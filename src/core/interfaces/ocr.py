"""OCR Provider 인터페이스"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Sequence

from PIL import Image


@dataclass
class BoundingBox:
    """텍스트 영역 바운딩 박스"""

    x: int
    y: int
    width: int
    height: int


@dataclass
class OCRResult:
    """OCR 인식 결과"""

    text: str
    confidence: float
    bounding_box: BoundingBox | None = None


class OCRProvider(ABC):
    """OCR 엔진 추상 인터페이스

    구현체 예시:
    - PaddleOCRProvider: PaddleOCR 기반 (추천)
    - TesseractProvider: Tesseract OCR
    - WindowsOCRProvider: Windows 내장 OCR
    """

    @abstractmethod
    async def recognize(self, image: Image.Image) -> list[OCRResult]:
        """이미지에서 텍스트 인식

        Args:
            image: PIL Image 객체

        Returns:
            list[OCRResult]: 인식된 텍스트 목록
        """
        pass

    @abstractmethod
    async def recognize_region(
        self, image: Image.Image, region: BoundingBox
    ) -> OCRResult | None:
        """지정된 영역에서 텍스트 인식

        Args:
            image: PIL Image 객체
            region: 인식할 영역

        Returns:
            OCRResult | None: 인식 결과 또는 None
        """
        pass

    @abstractmethod
    def get_supported_languages(self) -> list[str]:
        """지원하는 언어 목록 반환"""
        pass

    @abstractmethod
    def set_language(self, language: str) -> None:
        """인식 언어 설정"""
        pass
