"""GPT-SoVITS 합성 어댑터

기존 GPTSoVITSSynthesizer를 래핑하여 SynthesisAdapter 인터페이스 구현.
"""

import logging
from pathlib import Path

from ...interfaces import SynthesisAdapter, SynthesisRequest, SynthesisResult
from ...gpt_sovits.config import GPTSoVITSConfig
from ...gpt_sovits.model_manager import GPTSoVITSModelManager
from ...gpt_sovits.synthesizer import GPTSoVITSSynthesizer

logger = logging.getLogger(__name__)


class GPTSoVITSSynthesisAdapter(SynthesisAdapter):
    """GPT-SoVITS 합성 어댑터

    기존 GPTSoVITSSynthesizer를 래핑하여 SynthesisAdapter 인터페이스 구현.
    """

    engine_name = "gpt_sovits"
    supports_training = True
    requires_reference_audio = True

    def __init__(
        self,
        config: GPTSoVITSConfig | None = None,
        model_manager: GPTSoVITSModelManager | None = None,
    ):
        self.config = config or GPTSoVITSConfig()
        self._model_manager = model_manager or GPTSoVITSModelManager(self.config)
        self._synthesizer = GPTSoVITSSynthesizer(self.config, self._model_manager)

    async def is_available(self) -> bool:
        """API 서버 연결 확인"""
        return await self._synthesizer.api_client.is_api_running()

    async def ensure_ready(self) -> bool:
        """API 서버 준비 보장"""
        return await self._synthesizer.ensure_api_running()

    async def synthesize(self, request: SynthesisRequest) -> SynthesisResult | None:
        """텍스트를 음성으로 합성

        Args:
            request: 합성 요청 데이터

        Returns:
            합성 결과 또는 None (실패 시)
        """
        # 합성 파라미터 추출
        extra = request.extra_params or {}

        # 기존 synthesizer 사용
        result = await self._synthesizer.synthesize(
            char_id=request.voice_id,
            text=request.text,
            language=request.language,
            speed_factor=request.speed_factor,
            top_k=extra.get("top_k", self.config.top_k),
            top_p=extra.get("top_p", self.config.top_p),
            temperature=extra.get("temperature", self.config.temperature),
        )

        if not result:
            return None

        # 오디오 파일 읽기
        audio_data = result.audio_path.read_bytes()

        # SynthesisResult로 변환
        return SynthesisResult(
            audio_data=audio_data,
            sample_rate=result.sample_rate,
            duration=result.duration,
            engine=self.engine_name,
        )

    def get_available_voices(self) -> list[str]:
        """준비된 캐릭터 목록"""
        return self._model_manager.get_trained_characters()

    def is_voice_available(self, voice_id: str) -> bool:
        """캐릭터 준비 여부"""
        return self._model_manager.is_trained(voice_id)

    # 레거시 호환 프로퍼티
    @property
    def synthesizer(self) -> GPTSoVITSSynthesizer:
        """기존 synthesizer 접근 (레거시 호환)"""
        return self._synthesizer

    @property
    def model_manager(self) -> GPTSoVITSModelManager:
        """기존 model_manager 접근 (레거시 호환)"""
        return self._model_manager

    # force_zero_shot 모드 위임
    @property
    def force_zero_shot(self) -> bool:
        """제로샷 강제 모드"""
        return self._synthesizer.force_zero_shot

    def set_force_zero_shot(self, enabled: bool) -> None:
        """제로샷 강제 모드 설정"""
        self._synthesizer.set_force_zero_shot(enabled)

    async def shutdown(self) -> None:
        """리소스 정리"""
        await self._synthesizer.shutdown()
