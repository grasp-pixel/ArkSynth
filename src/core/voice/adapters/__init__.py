"""TTS 엔진 어댑터

각 TTS 엔진의 어댑터 구현체.
"""

from .gpt_sovits import (
    GPTSoVITSSynthesisAdapter,
    GPTSoVITSTrainingAdapter,
    GPTSoVITSModelAdapter,
)

__all__ = [
    # GPT-SoVITS
    "GPTSoVITSSynthesisAdapter",
    "GPTSoVITSTrainingAdapter",
    "GPTSoVITSModelAdapter",
]
