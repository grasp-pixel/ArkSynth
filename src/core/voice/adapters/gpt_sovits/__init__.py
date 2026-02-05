"""GPT-SoVITS 어댑터

기존 GPT-SoVITS 모듈을 래핑하여 어댑터 인터페이스 제공.
"""

from .synthesis import GPTSoVITSSynthesisAdapter
from .training import GPTSoVITSTrainingAdapter
from .model import GPTSoVITSModelAdapter

__all__ = [
    "GPTSoVITSSynthesisAdapter",
    "GPTSoVITSTrainingAdapter",
    "GPTSoVITSModelAdapter",
]
