"""OCR 모듈"""

from .paddle_ocr import PaddleOCRProvider
from .screen_capture import ScreenCapture, get_dialogue_region
from .dialogue_detector import DialogueDetector, DialogueDetection, DetectorConfig

__all__ = [
    "PaddleOCRProvider",
    "ScreenCapture",
    "get_dialogue_region",
    "DialogueDetector",
    "DialogueDetection",
    "DetectorConfig",
]
