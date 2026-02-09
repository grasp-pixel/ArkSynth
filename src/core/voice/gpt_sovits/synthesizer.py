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
        self._loaded_model_lang: str | None = None
        self._model_loaded = False
        self._api_started = False
        self._synthesizing = False  # 합성 진행 중 플래그
        self._force_zero_shot = False  # 제로샷 강제 모드 (테스트/비교용)

    async def ensure_api_running(self) -> bool:
        """API 서버가 실행 중인지 확인

        GPT-SoVITS API 서버는 사용자가 미리 실행해야 합니다.
        자동 시작하지 않습니다.

        Returns:
            bool: API 서버 준비 완료 여부
        """
        # 이미 실행 중인지 확인
        if await self.api_client.is_api_running():
            self._api_started = True
            return True

        # 실행 중이 아니면 에러
        logger.error(
            "GPT-SoVITS API 서버가 실행 중이 아닙니다. "
            "GPT-SoVITS를 먼저 실행하세요: "
            f"cd {self.config.gpt_sovits_path} && "
            f"runtime\\python.exe api_v2.py -a {self.config.api_host} -p {self.config.api_port}"
        )
        return False

    async def is_available(self, char_id: str, lang: str | None = None) -> bool:
        """해당 캐릭터 모델 사용 가능 여부"""
        return self.model_manager.is_trained(char_id, lang)

    @property
    def is_synthesizing(self) -> bool:
        """현재 음성 합성 진행 중 여부"""
        return self._synthesizing

    @property
    def force_zero_shot(self) -> bool:
        """제로샷 강제 모드 여부 (학습 모델 무시)"""
        return self._force_zero_shot

    def set_force_zero_shot(self, enabled: bool) -> None:
        """제로샷 강제 모드 설정

        True로 설정하면 학습된 모델이 있어도 제로샷 모드로 동작합니다.
        테스트/품질 비교용으로 사용합니다.
        """
        if self._force_zero_shot != enabled:
            self._force_zero_shot = enabled
            # 모드 변경 시 현재 로드된 모델 해제 (다음 합성 시 재로드)
            self._loaded_model_id = None
            self._loaded_model_lang = None
            self._model_loaded = False
            logger.info(f"제로샷 강제 모드: {'활성화' if enabled else '비활성화'}")

    async def load_model(self, char_id: str, lang: str | None = None) -> bool:
        """모델 로드

        이미 로드된 모델이면 스킵합니다.
        Zero-shot 모드에서는 사전 학습된 모델을 사용합니다.
        """
        if self._loaded_model_id == char_id and self._loaded_model_lang == lang and self._model_loaded:
            return True

        if not await self.is_available(char_id, lang):
            logger.error(f"모델이 존재하지 않음: {char_id} (lang={lang})")
            return False

        try:
            # API 서버 확인
            if not await self.ensure_api_running():
                logger.error("API 서버가 실행 중이 아닙니다")
                return False

            # Zero-shot 모드인지 확인
            # force_zero_shot이 활성화되면 학습 모델이 있어도 제로샷 사용
            has_trained = self.model_manager.has_trained_model(char_id, lang)
            is_zero_shot = self.model_manager.is_zero_shot_ready(char_id, lang) and \
                           (not has_trained or self._force_zero_shot)

            if is_zero_shot:
                # Zero-shot: 사전 학습된 모델 사용 (모델 로드 불필요)
                mode_reason = "강제 제로샷" if (has_trained and self._force_zero_shot) else "사전 학습 모델"
                logger.info(f"Zero-shot 모드: {char_id} ({mode_reason} 사용, lang={lang})")
                self._loaded_model_id = char_id
                self._loaded_model_lang = lang
                self._model_loaded = True
                return True
            else:
                # 학습된 모델 로드
                sovits_path = self.model_manager.get_sovits_path(char_id, lang)
                gpt_path = self.model_manager.get_gpt_path(char_id, lang)

                if not sovits_path or not gpt_path:
                    logger.error(f"모델 파일 없음: {char_id} (lang={lang})")
                    return False

                logger.info(f"학습된 모델 로드 중: {char_id} (lang={lang})")
                if await self.api_client.set_model(char_id, lang):
                    self._loaded_model_id = char_id
                    self._loaded_model_lang = lang
                    self._model_loaded = True
                    logger.info(f"모델 로드 완료: {char_id} (lang={lang})")
                    return True
                else:
                    logger.error(f"API를 통한 모델 로드 실패: {char_id}")
                    return False

        except Exception as e:
            logger.error(f"모델 로드 실패 ({char_id}): {e}")
            self._loaded_model_id = None
            self._loaded_model_lang = None
            self._model_loaded = False
            return False

    async def unload_model(self):
        """현재 모델 언로드"""
        if self._model_loaded:
            logger.info(f"모델 언로드: {self._loaded_model_id}")
            self._loaded_model_id = None
            self._loaded_model_lang = None
            self._model_loaded = False

    async def synthesize(
        self,
        char_id: str,
        text: str,
        output_path: Path | None = None,
        language: str = "ko",
        speed_factor: float = 1.0,
        top_k: int = 15,
        top_p: float = 1.0,
        temperature: float = 0.8,  # 낮은 온도로 안정성 향상
    ) -> SynthesisResult | None:
        """텍스트를 음성으로 합성

        Args:
            char_id: 캐릭터 ID
            text: 합성할 텍스트
            output_path: 출력 파일 경로 (없으면 자동 생성)
            language: 언어 코드 (ko, ja, zh, en)
            speed_factor: 음성 속도 (0.5~2.0)
            top_k: 샘플링 다양성 (1~20)
            top_p: Nucleus sampling (0.1~1.0)
            temperature: 음성 랜덤성 (0.1~2.0)

        Returns:
            SynthesisResult 또는 실패 시 None
        """
        # 모델 로드 확인 (캐릭터 또는 언어가 다르면 재로드)
        if self._loaded_model_id != char_id or self._loaded_model_lang != language:
            if not await self.load_model(char_id, language):
                return None

        # 출력 경로 설정
        if output_path is None:
            import hashlib

            text_hash = hashlib.md5(text.encode()).hexdigest()[:8]
            output_path = (
                self.config.get_model_path(char_id, language) / "outputs" / f"{text_hash}.wav"
            )
            output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            logger.info(f"[Synthesizer] 합성 시작: {char_id}")
            logger.info(f"[Synthesizer] 텍스트: {text[:50]}{'...' if len(text) > 50 else ''}")

            # API 서버 확인 (시작 전에만 체크, 합성 중에는 블로킹되므로 스킵)
            if not self._api_started:
                logger.error("GPT-SoVITS API 서버가 시작되지 않았습니다")
                return None

            # 합성 상태 플래그 설정
            self._synthesizing = True

            # 음성 합성
            success = await self.api_client.synthesize_to_file(
                text=text,
                char_id=char_id,
                output_path=output_path,
                language=language,
                speed_factor=speed_factor,
                top_k=top_k,
                top_p=top_p,
                temperature=temperature,
            )

            self._synthesizing = False

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
                logger.info(f"[Synthesizer] 합성 완료: {duration:.2f}초")
                return result
            else:
                logger.error("[Synthesizer] API 음성 합성 실패")
                return None

        except Exception as e:
            self._synthesizing = False
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
        if not await self.load_model(char_id, language):
            return

        for i, text in enumerate(texts):
            output_path = output_dir / f"{i:04d}.wav"
            result = await self.synthesize(
                char_id, text, output_path=output_path, language=language
            )
            yield i, result

    def get_reference_audio(self, char_id: str, lang: str | None = None) -> Path | None:
        """참조 오디오 경로 조회"""
        ref_dir = self.config.get_model_path(char_id, lang or self._loaded_model_lang) / "ref_audio"
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
        self._loaded_model_lang = None
        self._model_loaded = False


# 싱글톤 인스턴스
_synthesizer: GPTSoVITSSynthesizer | None = None


def get_synthesizer() -> GPTSoVITSSynthesizer:
    """합성기 싱글톤 인스턴스 반환"""
    global _synthesizer
    if _synthesizer is None:
        _synthesizer = GPTSoVITSSynthesizer()
    return _synthesizer


def reset_synthesizer() -> None:
    """합성기 싱글톤 리셋 (언어 변경 시)"""
    global _synthesizer
    _synthesizer = None
