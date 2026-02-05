"""GPT-SoVITS 음성 클로닝 모듈

Note: 새 코드에서는 adapters.gpt_sovits 사용을 권장합니다.
      어댑터 import: from src.core.voice.adapters.gpt_sovits import ...
"""

from .config import GPTSoVITSConfig
from .model_manager import GPTSoVITSModelManager
from .trainer import GPTSoVITSTrainer
from .training_manager import TrainingManager, TrainingJob, TrainingStatus
from .synthesizer import GPTSoVITSSynthesizer, SynthesisResult, get_synthesizer
from .installer import GPTSoVITSInstaller, InstallProgress, get_installer, reset_installer
from .audio_preprocessor import AudioPreprocessor, AudioSegment

__all__ = [
    "GPTSoVITSConfig",
    "GPTSoVITSModelManager",
    "GPTSoVITSTrainer",
    "TrainingManager",
    "TrainingJob",
    "TrainingStatus",
    "GPTSoVITSSynthesizer",
    "SynthesisResult",
    "get_synthesizer",
    "GPTSoVITSInstaller",
    "InstallProgress",
    "get_installer",
    "reset_installer",
    "AudioPreprocessor",
    "AudioSegment",
]
