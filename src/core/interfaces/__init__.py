"""ArkSynth 핵심 인터페이스 정의"""

from .tts import TTSProvider, TTSResult
from .ocr import OCRProvider, OCRResult, BoundingBox
from .cache import CacheProvider, CacheInfo, RenderProgress, RenderStatus
from .audio import AudioProvider, AudioInfo, PlaybackState

__all__ = [
    "TTSProvider",
    "TTSResult",
    "OCRProvider",
    "OCRResult",
    "BoundingBox",
    "CacheProvider",
    "CacheInfo",
    "RenderProgress",
    "RenderStatus",
    "AudioProvider",
    "AudioInfo",
    "PlaybackState",
]
