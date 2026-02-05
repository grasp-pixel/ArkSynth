"""학습 어댑터 인터페이스

TTS 엔진의 학습/준비 기능을 추상화하는 인터페이스.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable


class TrainingMode(str, Enum):
    """학습 모드"""

    PREPARE = "prepare"  # Zero-shot용 참조 오디오 준비
    FINETUNE = "finetune"  # 실제 모델 학습


@dataclass
class TrainingConfig:
    """학습 설정 데이터"""

    char_id: str
    char_name: str
    audio_dir: Path
    output_dir: Path
    mode: TrainingMode
    language: str = "ko"
    # 엔진별 추가 설정
    extra_config: dict = field(default_factory=dict)


@dataclass
class TrainingProgress:
    """학습 진행 상황 데이터"""

    stage: str  # "preprocessing", "training", "complete" 등
    progress: float  # 0.0 ~ 1.0
    current_epoch: int = 0
    total_epochs: int = 0
    message: str = ""


# 진행 상황 콜백 타입
ProgressCallback = Callable[[TrainingProgress], None]


class TrainingAdapter(ABC):
    """학습 어댑터 추상 클래스

    TTS 엔진의 학습/준비 기능을 위한 인터페이스.

    Attributes:
        engine_name: 엔진 이름
        supported_modes: 지원하는 학습 모드 목록
    """

    engine_name: str = ""
    supported_modes: list[TrainingMode] = []

    @abstractmethod
    def get_default_config(self, mode: TrainingMode) -> dict:
        """기본 설정 반환

        Args:
            mode: 학습 모드

        Returns:
            기본 설정 딕셔너리
        """
        pass

    @abstractmethod
    async def train(
        self,
        config: TrainingConfig,
        on_progress: ProgressCallback | None = None,
    ) -> bool:
        """학습 실행

        Args:
            config: 학습 설정
            on_progress: 진행 상황 콜백

        Returns:
            학습 성공 여부
        """
        pass

    @abstractmethod
    def cancel(self) -> None:
        """학습 취소"""
        pass

    def supports_mode(self, mode: TrainingMode) -> bool:
        """특정 학습 모드 지원 여부

        Args:
            mode: 학습 모드

        Returns:
            지원 여부
        """
        return mode in self.supported_modes
