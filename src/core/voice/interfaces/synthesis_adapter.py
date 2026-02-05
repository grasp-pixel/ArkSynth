"""합성 어댑터 인터페이스

TTS 엔진의 음성 합성 기능을 추상화하는 인터페이스.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SynthesisRequest:
    """합성 요청 데이터"""

    text: str
    voice_id: str  # char_id (캐릭터 ID)
    language: str = "ko"
    speed_factor: float = 1.0
    # 엔진별 추가 파라미터
    extra_params: dict = field(default_factory=dict)


@dataclass
class SynthesisResult:
    """합성 결과 데이터"""

    audio_data: bytes
    sample_rate: int
    duration: float  # 초
    engine: str  # "gpt_sovits", "qwen3_tts" 등


class SynthesisAdapter(ABC):
    """TTS 합성 어댑터 추상 클래스

    참조 오디오 기반 음성 클로닝 TTS 엔진을 위한 인터페이스.

    기존 TTSProvider(src/core/interfaces/tts.py)와의 차이점:
    - voice_id가 char_id로 명시적
    - 참조 오디오 기반 합성 전용
    - 엔진별 특성 지원 (supports_training 등)

    Attributes:
        engine_name: 엔진 이름 ("gpt_sovits", "qwen3_tts" 등)
        supports_training: 학습 지원 여부
        requires_reference_audio: 참조 오디오 필수 여부
    """

    engine_name: str = ""
    supports_training: bool = False
    requires_reference_audio: bool = True

    @abstractmethod
    async def is_available(self) -> bool:
        """엔진 사용 가능 여부 확인

        API 서버 연결, 모델 로드 상태 등을 확인합니다.

        Returns:
            사용 가능 여부
        """
        pass

    @abstractmethod
    async def synthesize(self, request: SynthesisRequest) -> SynthesisResult | None:
        """텍스트를 음성으로 합성

        Args:
            request: 합성 요청 데이터

        Returns:
            합성 결과 또는 None (실패 시)
        """
        pass

    @abstractmethod
    def get_available_voices(self) -> list[str]:
        """사용 가능한 음성(캐릭터) 목록

        Returns:
            준비된 캐릭터 ID 목록
        """
        pass

    @abstractmethod
    def is_voice_available(self, voice_id: str) -> bool:
        """특정 음성 사용 가능 여부

        Args:
            voice_id: 캐릭터 ID

        Returns:
            사용 가능 여부
        """
        pass

    async def ensure_ready(self) -> bool:
        """엔진 준비 보장

        필요한 경우 API 서버 시작 등의 초기화를 수행합니다.
        기본 구현은 is_available()을 호출합니다.

        Returns:
            준비 완료 여부
        """
        return await self.is_available()
