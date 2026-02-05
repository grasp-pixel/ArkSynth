"""TTS 어댑터 인터페이스

여러 TTS 엔진을 통합하기 위한 추상 인터페이스 정의.
"""

from .synthesis_adapter import SynthesisAdapter, SynthesisRequest, SynthesisResult
from .training_adapter import TrainingAdapter, TrainingConfig, TrainingMode, TrainingProgress
from .model_adapter import ModelAdapter, ModelInfo, ModelType

__all__ = [
    # 합성 어댑터
    "SynthesisAdapter",
    "SynthesisRequest",
    "SynthesisResult",
    # 학습 어댑터
    "TrainingAdapter",
    "TrainingConfig",
    "TrainingMode",
    "TrainingProgress",
    # 모델 어댑터
    "ModelAdapter",
    "ModelInfo",
    "ModelType",
]
