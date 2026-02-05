"""모델 관리 어댑터 인터페이스

TTS 엔진의 모델 관리 기능을 추상화하는 인터페이스.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path


class ModelType(str, Enum):
    """모델 타입"""

    NONE = "none"  # 준비되지 않음
    PREPARED = "prepared"  # Zero-shot 준비됨 (참조 오디오만)
    FINETUNED = "finetuned"  # Fine-tuning 완료


@dataclass
class ModelInfo:
    """모델 정보 데이터"""

    char_id: str
    char_name: str
    model_type: ModelType
    trained_at: datetime | None
    language: str
    engine: str  # "gpt_sovits", "qwen3_tts" 등
    # 엔진별 추가 정보
    extra_info: dict = field(default_factory=dict)


class ModelAdapter(ABC):
    """모델 관리 어댑터 추상 클래스

    TTS 엔진의 모델 관리 기능을 위한 인터페이스.

    Attributes:
        engine_name: 엔진 이름
        models_path: 모델 저장 경로
    """

    engine_name: str = ""
    models_path: Path = Path("models")

    @abstractmethod
    def get_model_type(self, char_id: str) -> ModelType:
        """모델 타입 조회

        Args:
            char_id: 캐릭터 ID

        Returns:
            모델 타입 (NONE, PREPARED, FINETUNED)
        """
        pass

    @abstractmethod
    def is_ready(self, char_id: str) -> bool:
        """모델 사용 가능 여부

        PREPARED 또는 FINETUNED 상태면 사용 가능.

        Args:
            char_id: 캐릭터 ID

        Returns:
            사용 가능 여부
        """
        pass

    @abstractmethod
    def list_models(self) -> list[ModelInfo]:
        """모든 모델 목록

        Returns:
            모델 정보 목록
        """
        pass

    @abstractmethod
    def delete_model(self, char_id: str) -> bool:
        """모델 삭제

        Args:
            char_id: 캐릭터 ID

        Returns:
            삭제 성공 여부
        """
        pass

    def get_model_info(self, char_id: str) -> ModelInfo | None:
        """특정 모델 정보 조회

        Args:
            char_id: 캐릭터 ID

        Returns:
            모델 정보 또는 None
        """
        for model in self.list_models():
            if model.char_id == char_id:
                return model
        return None
