"""ArkSynth 핵심 인터페이스 정의"""

from .ocr import OCRProvider, OCRResult, BoundingBox

__all__ = [
    "OCRProvider",
    "OCRResult",
    "BoundingBox",
]
