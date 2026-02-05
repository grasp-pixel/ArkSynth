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

# Qwen3-TTS 어댑터는 구현 시 추가
# from .qwen3_tts import (
#     Qwen3TTSSynthesisAdapter,
#     Qwen3TTSTrainingAdapter,
#     Qwen3TTSModelAdapter,
# )
