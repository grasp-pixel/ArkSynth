"""GPT-SoVITS 음성 합성기"""

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator

from .config import GPTSoVITSConfig
from .model_manager import GPTSoVITSModelManager
from .api_client import GPTSoVITSAPIClient

logger = logging.getLogger(__name__)


@dataclass
class SynthesisResult:
    """음성 합성 결과"""

    char_id: str
    text: str
    audio_path: Path
    duration: float  # 초 단위
    sample_rate: int


class GPTSoVITSSynthesizer:
    """GPT-SoVITS 음성 합성기

    GPT-SoVITS API 서버를 통해 텍스트를 음성으로 합성합니다.
    """

    def __init__(
        self,
        config: GPTSoVITSConfig | None = None,
        model_manager: GPTSoVITSModelManager | None = None,
    ):
        self.config = config or GPTSoVITSConfig()
        self.model_manager = model_manager or GPTSoVITSModelManager(self.config)
        self.api_client = GPTSoVITSAPIClient(self.config)

        # 현재 로드된 모델 캐시
        self._loaded_model_id: str | None = None
        self._model_loaded = False
        self._api_started = False

    async def ensure_api_running(self) -> bool:
        """API 서버가 실행 중인지 확인하고 필요 시 시작

        Returns:
            bool: API 서버 준비 완료 여부
        """
        # 이미 실행 중인지 확인
        if await self.api_client.is_api_running():
            self._api_started = True
            return True

        # GPT-SoVITS 설치 확인
        if not self.config.is_gpt_sovits_installed:
            logger.error(f"GPT-SoVITS가 설치되어 있지 않습니다: {self.config.gpt_sovits_path}")
            return False

        # API 서버 시작
        if not self.api_client.start_api_server():
            logger.error("GPT-SoVITS API 서버 시작 실패")
            return False

        # 준비될 때까지 대기
        if await self.api_client.wait_for_api_ready(timeout=60.0):
            self._api_started = True
            return True

        logger.error("GPT-SoVITS API 서버 준비 시간 초과")
        return False

    async def is_available(self, char_id: str) -> bool:
        """해당 캐릭터 모델 사용 가능 여부"""
        return self.model_manager.is_trained(char_id)

    async def load_model(self, char_id: str) -> bool:
        """모델 로드

        이미 로드된 모델이면 스킵합니다.
        Zero-shot 모드에서는 사전 학습된 모델을 사용합니다.
        """
        if self._loaded_model_id == char_id and self._model_loaded:
            return True

        if not await self.is_available(char_id):
            logger.error(f"모델이 존재하지 않음: {char_id}")
            return False

        try:
            # API 서버 확인
            if not await self.ensure_api_running():
                logger.error("API 서버가 실행 중이 아닙니다")
                return False

            # Zero-shot 모드인지 확인
            is_zero_shot = self.model_manager.is_zero_shot_ready(char_id) and \
                           not self.model_manager.has_trained_model(char_id)

            if is_zero_shot:
                # Zero-shot: 사전 학습된 모델 사용 (모델 로드 불필요)
                logger.info(f"Zero-shot 모드: {char_id} (사전 학습 모델 사용)")
                self._loaded_model_id = char_id
                self._model_loaded = True
                return True
            else:
                # 학습된 모델 로드
                sovits_path = self.model_manager.get_sovits_path(char_id)
                gpt_path = self.model_manager.get_gpt_path(char_id)

                if not sovits_path or not gpt_path:
                    logger.error(f"모델 파일 없음: {char_id}")
                    return False

                logger.info(f"학습된 모델 로드 중: {char_id}")
                if await self.api_client.set_model(char_id):
                    self._loaded_model_id = char_id
                    self._model_loaded = True
                    logger.info(f"모델 로드 완료: {char_id}")
                    return True
                else:
                    logger.error(f"API를 통한 모델 로드 실패: {char_id}")
                    return False

        except Exception as e:
            logger.error(f"모델 로드 실패 ({char_id}): {e}")
            self._loaded_model_id = None
            self._model_loaded = False
            return False

    async def unload_model(self):
        """현재 모델 언로드"""
        if self._model_loaded:
            logger.info(f"모델 언로드: {self._loaded_model_id}")
            self._loaded_model_id = None
            self._model_loaded = False

    async def synthesize(
        self,
        char_id: str,
        text: str,
        output_path: Path | None = None,
        language: str = "ko",
    ) -> SynthesisResult | None:
        """텍스트를 음성으로 합성

        Args:
            char_id: 캐릭터 ID
            text: 합성할 텍스트
            output_path: 출력 파일 경로 (없으면 자동 생성)
            language: 언어 코드 (ko, ja, zh, en)

        Returns:
            SynthesisResult 또는 실패 시 None
        """
        # 모델 로드 확인
        if self._loaded_model_id != char_id:
            if not await self.load_model(char_id):
                return None

        # 출력 경로 설정
        if output_path is None:
            import hashlib

            text_hash = hashlib.md5(text.encode()).hexdigest()[:8]
            output_path = (
                self.config.models_path / char_id / "outputs" / f"{text_hash}.wav"
            )
            output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            logger.info(f"음성 합성 중: {char_id} - {text[:20]}...")

            # API 서버 확인
            if not self._api_started or not await self.api_client.is_api_running():
                logger.error("GPT-SoVITS API 서버가 실행 중이 아닙니다")
                return None

            # 음성 합성
            success = await self.api_client.synthesize_to_file(
                text=text,
                char_id=char_id,
                output_path=output_path,
                language=language,
            )

            if success:
                # 오디오 파일에서 실제 길이 계산
                duration = self._get_audio_duration(output_path)
                result = SynthesisResult(
                    char_id=char_id,
                    text=text,
                    audio_path=output_path,
                    duration=duration,
                    sample_rate=self.config.sample_rate,
                )
                logger.info(f"음성 합성 완료: {output_path}")
                return result
            else:
                logger.error("API 음성 합성 실패")
                return None

        except Exception as e:
            logger.error(f"음성 합성 실패: {e}")
            return None

    async def synthesize_batch(
        self,
        char_id: str,
        texts: list[str],
        output_dir: Path,
        language: str = "ko",
    ) -> AsyncIterator[tuple[int, SynthesisResult | None]]:
        """여러 텍스트를 순차적으로 합성

        Args:
            char_id: 캐릭터 ID
            texts: 합성할 텍스트 목록
            output_dir: 출력 디렉토리
            language: 언어 코드

        Yields:
            (인덱스, SynthesisResult) 튜플
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        # 모델 미리 로드
        if not await self.load_model(char_id):
            return

        for i, text in enumerate(texts):
            output_path = output_dir / f"{i:04d}.wav"
            result = await self.synthesize(
                char_id, text, output_path=output_path, language=language
            )
            yield i, result

    def get_reference_audio(self, char_id: str) -> Path | None:
        """참조 오디오 경로 조회"""
        ref_dir = self.config.get_model_path(char_id) / "ref_audio"
        if not ref_dir.exists():
            return None

        # 첫 번째 참조 오디오 반환
        for audio_file in ref_dir.iterdir():
            if audio_file.suffix.lower() in (".wav", ".mp3"):
                return audio_file

        return None

    def _get_audio_duration(self, path: Path) -> float:
        """오디오 파일 길이 계산 (초)"""
        try:
            import wave

            with wave.open(str(path), "rb") as wav_file:
                frames = wav_file.getnframes()
                rate = wav_file.getframerate()
                return frames / float(rate)
        except Exception as e:
            logger.warning(f"오디오 길이 계산 실패: {e}")
            return 0.0

    async def shutdown(self):
        """리소스 정리"""
        await self.api_client.close()
        self._api_started = False
        self._loaded_model_id = None
        self._model_loaded = False


# 싱글톤 인스턴스
_synthesizer: GPTSoVITSSynthesizer | None = None


def get_synthesizer() -> GPTSoVITSSynthesizer:
    """합성기 싱글톤 인스턴스 반환"""
    global _synthesizer
    if _synthesizer is None:
        _synthesizer = GPTSoVITSSynthesizer()
    return _synthesizer
