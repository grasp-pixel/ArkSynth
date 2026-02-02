"""OCR 모듈

EasyOCR 기반 - 한국어 인식 성능 우수
다양한 폰트/스타일 지원, 띄어쓰기 인식
+ 스토리 데이터 퍼지 매칭
"""

from .easyocr_provider import EasyOCRProvider, RapidOCRProvider, PaddleOCRProvider
from .screen_capture import ScreenCapture, WindowInfo, get_dialogue_region
from .dialogue_detector import DialogueDetector, DialogueDetection, DetectorConfig
from .dialogue_matcher import DialogueMatcher, MatchResult

__all__ = [
    "EasyOCRProvider",
    "RapidOCRProvider",  # 호환성을 위한 별칭
    "PaddleOCRProvider",  # 호환성을 위한 별칭
    "ScreenCapture",
    "WindowInfo",
    "get_dialogue_region",
    "DialogueDetector",
    "DialogueDetection",
    "DetectorConfig",
    "DialogueMatcher",
    "MatchResult",
]
