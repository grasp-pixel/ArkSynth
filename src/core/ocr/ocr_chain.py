"""OCR 폴백 체인

우선순위 기반 다중 영역 OCR 지원.
하단 대사 영역 실패 시 화면 중앙 자막 영역으로 폴백.
"""

from dataclasses import dataclass

from PIL import Image

from .easyocr_provider import EasyOCRProvider
from .screen_capture import (
    OCRRegionType,
    get_dialogue_region,
    get_subtitle_region,
)
from ..interfaces.ocr import BoundingBox


@dataclass
class OCRRegionResult:
    """OCR 영역별 인식 결과"""

    success: bool
    region_type: OCRRegionType
    text: str = ""
    confidence: float = 0.0
    region: BoundingBox | None = None


@dataclass
class OCRRegionConfig:
    """OCR 영역 설정"""

    type: OCRRegionType
    priority: int  # 낮을수록 먼저 시도
    min_confidence: float = 0.3
    min_text_length: int = 2


# 기본 폴백 체인 설정: 대사 영역 → 자막 영역
DEFAULT_FALLBACK_CHAIN: list[OCRRegionConfig] = [
    OCRRegionConfig(type=OCRRegionType.DIALOGUE, priority=1),
    OCRRegionConfig(type=OCRRegionType.SUBTITLE, priority=2),
]


class OCRFallbackChain:
    """OCR 폴백 체인

    우선순위 순으로 영역을 시도하고, 첫 번째 성공 결과 반환.
    """

    def __init__(
        self,
        ocr_provider: EasyOCRProvider,
        regions: list[OCRRegionConfig] | None = None,
    ):
        """초기화

        Args:
            ocr_provider: OCR 엔진
            regions: 영역 설정 목록 (None이면 기본값 사용)
        """
        self._ocr = ocr_provider
        self._regions = sorted(
            regions or DEFAULT_FALLBACK_CHAIN,
            key=lambda r: r.priority,
        )

    def _get_region_bbox(
        self, region_type: OCRRegionType, width: int, height: int
    ) -> BoundingBox:
        """영역 타입에 따른 바운딩 박스 반환"""
        if region_type == OCRRegionType.DIALOGUE:
            return get_dialogue_region(width, height)
        elif region_type == OCRRegionType.SUBTITLE:
            return get_subtitle_region(width, height)
        else:
            raise ValueError(f"Unknown region type: {region_type}")

    async def _try_region(
        self, image: Image.Image, config: OCRRegionConfig
    ) -> OCRRegionResult:
        """단일 영역 OCR 시도

        전체 텍스트 OCR 후 DialogueMatcher로 스토리 데이터 매칭.
        화자 정보는 스토리 데이터에서 가져옴 (색상 분리 불필요).
        """
        bbox = self._get_region_bbox(config.type, image.width, image.height)

        # 영역 크롭
        cropped = image.crop((
            bbox.x,
            bbox.y,
            bbox.x + bbox.width,
            bbox.y + bbox.height,
        ))

        try:
            # 전체 텍스트 OCR (색상 분리 없이)
            # 화자 정보는 DialogueMatcher가 스토리 데이터에서 가져옴
            text = await self._ocr.recognize_all_text(cropped)

            # 신뢰도: 텍스트 길이 기반 추정
            confidence = 0.7 if text else 0.0

            if (
                text
                and len(text) >= config.min_text_length
                and confidence >= config.min_confidence
            ):
                return OCRRegionResult(
                    success=True,
                    region_type=config.type,
                    text=text,
                    confidence=confidence,
                    region=bbox,
                )

        except Exception as e:
            print(f"[OCRChain] {config.type.value} 영역 OCR 실패: {e}")

        return OCRRegionResult(
            success=False,
            region_type=config.type,
            region=bbox,
        )

    async def recognize(self, image: Image.Image) -> OCRRegionResult:
        """폴백 체인으로 OCR 실행

        우선순위 순으로 영역을 시도하고, 첫 번째 성공 결과 반환.

        Args:
            image: 전체 화면 이미지

        Returns:
            OCR 결과 (성공/실패 포함)
        """
        for config in self._regions:
            print(f"[OCRChain] {config.type.value} 영역 시도 중...", flush=True)
            result = await self._try_region(image, config)

            if result.success:
                print(
                    f"[OCRChain] {config.type.value} 영역에서 인식 성공: "
                    f"'{result.text[:30]}...' (신뢰도: {result.confidence:.2f})",
                    flush=True,
                )
                return result

            print(f"[OCRChain] {config.type.value} 영역 실패, 다음 영역 시도", flush=True)

        # 모든 영역 실패
        print("[OCRChain] 모든 영역에서 인식 실패", flush=True)
        return OCRRegionResult(
            success=False,
            region_type=self._regions[0].type if self._regions else OCRRegionType.DIALOGUE,
        )

    async def recognize_all_regions(
        self, image: Image.Image
    ) -> dict[OCRRegionType, OCRRegionResult]:
        """모든 영역 OCR 실행 (미리보기용)

        Args:
            image: 전체 화면 이미지

        Returns:
            영역별 OCR 결과 딕셔너리
        """
        results = {}
        for config in self._regions:
            result = await self._try_region(image, config)
            results[config.type] = result
        return results

    def get_all_regions(
        self, width: int, height: int
    ) -> dict[OCRRegionType, BoundingBox]:
        """모든 영역의 바운딩 박스 반환 (미리보기용)"""
        return {
            config.type: self._get_region_bbox(config.type, width, height)
            for config in self._regions
        }
