"""TTS 통합 매니저

여러 TTS 엔진을 통합 관리하는 매니저.
"""

from .tts_manager import TTSManager, get_tts_manager
from .training_manager import UnifiedTrainingManager, get_unified_training_manager

__all__ = [
    "TTSManager",
    "get_tts_manager",
    "UnifiedTrainingManager",
    "get_unified_training_manager",
]
