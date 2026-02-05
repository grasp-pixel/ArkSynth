"""TTS 통합 매니저

여러 TTS 엔진을 통합 관리하고 엔진 선택 로직 제공.
"""

import logging
from typing import Literal

from ..interfaces import SynthesisAdapter, SynthesisRequest, SynthesisResult
from ..adapters.gpt_sovits import GPTSoVITSSynthesisAdapter

logger = logging.getLogger(__name__)

EngineType = Literal["gpt_sovits", "qwen3_tts", "auto"]


class TTSManager:
    """TTS 통합 매니저

    여러 TTS 엔진을 관리하고 엔진 선택 로직을 제공합니다.

    기능:
    - 여러 TTS 엔진 관리
    - 엔진 자동 선택 (모델 가용성 기반)
    - 폴백 처리
    """

    def __init__(self):
        self._adapters: dict[str, SynthesisAdapter] = {}
        self._default_engine: str = "gpt_sovits"
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """어댑터 초기화 (lazy)"""
        if self._initialized:
            return

        # GPT-SoVITS는 항상 초기화
        try:
            self._adapters["gpt_sovits"] = GPTSoVITSSynthesisAdapter()
            logger.info("GPT-SoVITS 어댑터 초기화 완료")
        except Exception as e:
            logger.error(f"GPT-SoVITS 어댑터 초기화 실패: {e}")

        # Qwen3-TTS 초기화 (선택적)
        try:
            from ..adapters.qwen3_tts import Qwen3TTSSynthesisAdapter
            self._adapters["qwen3_tts"] = Qwen3TTSSynthesisAdapter()
            logger.info("Qwen3-TTS 어댑터 초기화 완료")
        except ImportError as e:
            logger.debug(f"Qwen3-TTS 어댑터 초기화 스킵 (qwen-tts 미설치): {e}")
        except Exception as e:
            logger.warning(f"Qwen3-TTS 어댑터 초기화 실패: {e}")

        self._initialized = True

    def get_adapter(self, engine: str) -> SynthesisAdapter | None:
        """특정 엔진 어댑터 반환

        Args:
            engine: 엔진 이름

        Returns:
            어댑터 또는 None
        """
        self._ensure_initialized()
        return self._adapters.get(engine)

    def get_available_engines(self) -> list[str]:
        """사용 가능한 엔진 목록"""
        self._ensure_initialized()
        return list(self._adapters.keys())

    async def select_engine(
        self,
        voice_id: str,
        preferred: EngineType = "auto",
    ) -> str | None:
        """최적 엔진 선택

        Args:
            voice_id: 캐릭터 ID
            preferred: 선호 엔진 ("auto"면 자동 선택)

        Returns:
            선택된 엔진 이름 또는 None
        """
        self._ensure_initialized()

        if preferred != "auto" and preferred in self._adapters:
            adapter = self._adapters[preferred]
            if adapter.is_voice_available(voice_id):
                return preferred

        # 자동 선택: 모델이 준비된 엔진 선택
        for engine, adapter in self._adapters.items():
            if adapter.is_voice_available(voice_id):
                return engine

        # 기본 엔진 반환 (준비는 안 됐지만)
        if self._default_engine in self._adapters:
            return self._default_engine

        return None

    async def synthesize(
        self,
        request: SynthesisRequest,
        engine: EngineType = "auto",
    ) -> SynthesisResult | None:
        """텍스트를 음성으로 합성

        Args:
            request: 합성 요청
            engine: 사용할 엔진 ("auto"면 자동 선택)

        Returns:
            합성 결과 또는 None
        """
        selected_engine = await self.select_engine(request.voice_id, engine)
        if not selected_engine:
            logger.error(f"사용 가능한 TTS 엔진이 없습니다: {request.voice_id}")
            return None

        adapter = self._adapters[selected_engine]

        # 엔진 가용성 확인
        if not await adapter.is_available():
            logger.warning(f"{selected_engine} 엔진이 사용 불가 상태입니다")
            # 다른 엔진 시도
            for alt_engine, alt_adapter in self._adapters.items():
                if alt_engine != selected_engine and await alt_adapter.is_available():
                    if alt_adapter.is_voice_available(request.voice_id):
                        logger.info(f"대체 엔진 사용: {alt_engine}")
                        return await alt_adapter.synthesize(request)
            return None

        return await adapter.synthesize(request)

    def get_all_available_voices(self) -> dict[str, list[str]]:
        """모든 엔진의 사용 가능한 음성 목록

        Returns:
            {엔진: [캐릭터 ID 목록]} 딕셔너리
        """
        self._ensure_initialized()
        result = {}
        for engine, adapter in self._adapters.items():
            result[engine] = adapter.get_available_voices()
        return result

    def is_voice_available(self, voice_id: str, engine: EngineType = "auto") -> bool:
        """음성 사용 가능 여부

        Args:
            voice_id: 캐릭터 ID
            engine: 엔진 ("auto"면 아무 엔진에서나)

        Returns:
            사용 가능 여부
        """
        self._ensure_initialized()

        if engine != "auto":
            adapter = self._adapters.get(engine)
            return adapter.is_voice_available(voice_id) if adapter else False

        # auto: 아무 엔진에서나 사용 가능하면 True
        for adapter in self._adapters.values():
            if adapter.is_voice_available(voice_id):
                return True
        return False


# 싱글톤 인스턴스
_tts_manager: TTSManager | None = None


def get_tts_manager() -> TTSManager:
    """TTS 매니저 싱글톤 인스턴스 반환"""
    global _tts_manager
    if _tts_manager is None:
        _tts_manager = TTSManager()
    return _tts_manager
