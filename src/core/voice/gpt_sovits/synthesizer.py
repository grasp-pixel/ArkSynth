"""GPT-SoVITS 음성 합성기"""

import asyncio
import logging
import random
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator

from .config import GPTSoVITSConfig
from .model_manager import GPTSoVITSModelManager

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

    학습된 모델을 사용하여 텍스트를 음성으로 합성합니다.
    """

    def __init__(
        self,
        config: GPTSoVITSConfig | None = None,
        model_manager: GPTSoVITSModelManager | None = None,
    ):
        self.config = config or GPTSoVITSConfig()
        self.model_manager = model_manager or GPTSoVITSModelManager(self.config)

        # 현재 로드된 모델 캐시
        self._loaded_model_id: str | None = None
        self._model_loaded = False

    async def is_available(self, char_id: str) -> bool:
        """해당 캐릭터 모델 사용 가능 여부"""
        return self.model_manager.is_trained(char_id)

    async def load_model(self, char_id: str) -> bool:
        """모델 로드

        이미 로드된 모델이면 스킵합니다.
        """
        if self._loaded_model_id == char_id and self._model_loaded:
            return True

        if not await self.is_available(char_id):
            logger.error(f"모델이 존재하지 않음: {char_id}")
            return False

        sovits_path = self.model_manager.get_sovits_path(char_id)
        gpt_path = self.model_manager.get_gpt_path(char_id)

        if not sovits_path or not gpt_path:
            logger.error(f"모델 파일 없음: {char_id}")
            return False

        try:
            # TODO: 실제 GPT-SoVITS 모델 로드
            # 현재는 시뮬레이션 모드
            logger.info(f"모델 로드 중: {char_id}")
            await asyncio.sleep(0.1)  # 시뮬레이션

            self._loaded_model_id = char_id
            self._model_loaded = True
            logger.info(f"모델 로드 완료: {char_id}")
            return True

        except Exception as e:
            logger.error(f"모델 로드 실패 ({char_id}): {e}")
            self._loaded_model_id = None
            self._model_loaded = False
            return False

    async def unload_model(self):
        """현재 모델 언로드"""
        if self._model_loaded:
            logger.info(f"모델 언로드: {self._loaded_model_id}")
            # TODO: 실제 모델 언로드 (메모리 해제)
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
            # TODO: 실제 GPT-SoVITS 합성
            # 현재는 시뮬레이션 모드 - 더미 파일 생성
            logger.info(f"음성 합성 중: {char_id} - {text[:20]}...")

            # 시뮬레이션: 텍스트 길이 기반 예상 길이
            estimated_duration = len(text) * 0.1  # 글자당 0.1초

            await asyncio.sleep(0.2)  # 합성 시뮬레이션

            # 더미 WAV 파일 생성 (실제 구현 시 제거)
            if not output_path.exists():
                self._create_dummy_wav(output_path, estimated_duration)

            result = SynthesisResult(
                char_id=char_id,
                text=text,
                audio_path=output_path,
                duration=estimated_duration,
                sample_rate=self.config.sample_rate,
            )

            logger.info(f"음성 합성 완료: {output_path}")
            return result

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

    def _create_dummy_wav(self, path: Path, duration: float):
        """더미 WAV 파일 생성 (테스트용)"""
        try:
            import wave
            import struct

            sample_rate = self.config.sample_rate
            num_samples = int(sample_rate * duration)

            with wave.open(str(path), "w") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(sample_rate)

                # 무음 데이터 생성
                silence = struct.pack("<h", 0) * num_samples
                wav_file.writeframes(silence)

        except Exception as e:
            logger.warning(f"더미 WAV 생성 실패: {e}")
            # 빈 파일 생성
            path.touch()


# 싱글톤 인스턴스
_synthesizer: GPTSoVITSSynthesizer | None = None


def get_synthesizer() -> GPTSoVITSSynthesizer:
    """합성기 싱글톤 인스턴스 반환"""
    global _synthesizer
    if _synthesizer is None:
        _synthesizer = GPTSoVITSSynthesizer()
    return _synthesizer
