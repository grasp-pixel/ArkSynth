"""EasyOCR 기반 OCR Provider 구현

EasyOCR: 딥러닝 기반 OCR
- 한국어 인식 성능 우수
- 다양한 폰트/스타일 지원
- 띄어쓰기 인식 잘 됨
- GPU 가속 지원
"""

import asyncio
from functools import lru_cache
from typing import Any

import numpy as np
from PIL import Image

from ..interfaces.ocr import BoundingBox, OCRProvider, OCRResult


def _detect_gpu() -> bool:
    """CUDA GPU 사용 가능 여부 감지"""
    try:
        import torch
        available = torch.cuda.is_available()
        if available:
            print(f"[EasyOCR] CUDA GPU 감지: {torch.cuda.get_device_name(0)}")
        return available
    except ImportError:
        return False


# GPU 사용 여부 캐싱 (앱 시작 시 한 번만 체크)
_GPU_AVAILABLE: bool | None = None


def is_gpu_available() -> bool:
    """GPU 사용 가능 여부 반환 (캐싱됨)"""
    global _GPU_AVAILABLE
    if _GPU_AVAILABLE is None:
        _GPU_AVAILABLE = _detect_gpu()
    return _GPU_AVAILABLE


class EasyOCRProvider(OCRProvider):
    """EasyOCR 기반 OCR 엔진

    명일방주 게임 화면에서 대사를 인식하도록 최적화.
    한국어/중국어/일본어/영어 지원.
    """

    # 언어 코드 매핑 (EasyOCR 형식)
    LANGUAGE_MAP = {
        "ko": ["ko", "en"],  # 한국어 + 영어 (혼용 지원)
        "ko_KR": ["ko", "en"],
        "zh": ["ch_sim", "en"],  # 중국어 간체
        "zh_CN": ["ch_sim", "en"],
        "zh_TW": ["ch_tra", "en"],  # 중국어 번체
        "ja": ["ja", "en"],  # 일본어
        "ja_JP": ["ja", "en"],
        "en": ["en"],
        "en_US": ["en"],
    }

    def __init__(
        self,
        language: str = "ko",
        use_gpu: bool | None = None,
        max_width: int = 1920,
    ):
        """초기화

        Args:
            language: 인식 언어 (ko, zh, ja, en)
            use_gpu: GPU 사용 여부 (None이면 자동 감지)
            max_width: OCR 전 이미지 최대 너비 (리사이즈, 0이면 비활성화)
        """
        self._language = language
        self._use_gpu = use_gpu if use_gpu is not None else is_gpu_available()
        self._max_width = max_width
        self._reader: Any = None  # lazy loading

        if self._use_gpu:
            print(f"[EasyOCR] GPU 모드 활성화")
        else:
            print(f"[EasyOCR] CPU 모드 (이미지 리사이즈: max_width={max_width})")

    def _get_lang_list(self, lang: str) -> list[str]:
        """언어 코드를 EasyOCR 언어 리스트로 변환"""
        return self.LANGUAGE_MAP.get(lang, ["ko", "en"])

    @lru_cache(maxsize=4)
    def _get_reader(self, lang_tuple: tuple) -> Any:
        """EasyOCR Reader 가져오기 (캐싱)"""
        try:
            lang_list = list(lang_tuple)
            print(f"[EasyOCR] Loading reader for languages: {lang_list}")
            import easyocr

            reader = easyocr.Reader(
                lang_list,
                gpu=self._use_gpu,
                verbose=False,
            )
            print(f"[EasyOCR] Reader loaded successfully")
            return reader
        except Exception as e:
            print(f"[EasyOCR] Failed to load reader: {e}")
            import traceback
            traceback.print_exc()
            raise

    @property
    def reader(self) -> Any:
        """EasyOCR Reader (lazy loading)"""
        if self._reader is None:
            lang_list = self._get_lang_list(self._language)
            self._reader = self._get_reader(tuple(lang_list))
        return self._reader

    def _image_to_array(self, image: Image.Image) -> np.ndarray:
        """PIL Image를 numpy array로 변환"""
        if image.mode != "RGB":
            image = image.convert("RGB")
        return np.array(image)

    def _preprocess_for_ocr(self, image: Image.Image) -> Image.Image:
        """OCR 전처리: 대비 향상 및 선명화

        게임 화면의 흰색/밝은 텍스트 인식 개선.
        """
        import cv2
        from PIL import ImageEnhance

        # 1. 대비 향상
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(1.5)  # 대비 1.5배

        # 2. 선명도 향상
        enhancer = ImageEnhance.Sharpness(image)
        image = enhancer.enhance(2.0)  # 선명도 2배

        # 3. OpenCV로 추가 전처리
        img_array = np.array(image)

        # 그레이스케일 변환
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)

        # CLAHE (적응형 히스토그램 평활화) - 국소적 대비 향상
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)

        # 다시 RGB로 변환 (EasyOCR은 컬러 이미지도 받음)
        enhanced_rgb = cv2.cvtColor(enhanced, cv2.COLOR_GRAY2RGB)

        return Image.fromarray(enhanced_rgb)

    def _resize_image(self, image: Image.Image) -> Image.Image:
        """이미지 리사이즈 (OCR 성능 최적화)

        max_width보다 큰 이미지는 비율 유지하며 축소.
        GPU 모드에서는 리사이즈 하지 않음 (GPU가 충분히 빠름).
        """
        if self._max_width <= 0 or self._use_gpu:
            return image

        if image.width <= self._max_width:
            return image

        ratio = self._max_width / image.width
        new_height = int(image.height * ratio)
        resized = image.resize((self._max_width, new_height), Image.Resampling.LANCZOS)
        print(f"[EasyOCR] 이미지 리사이즈: {image.width}x{image.height} → {resized.width}x{resized.height}")
        return resized

    def _run_ocr(self, img_array: np.ndarray) -> list:
        """OCR 실행 (동기)"""
        # EasyOCR readtext 실행
        # detail=1: 바운딩 박스 + 텍스트 + 신뢰도 반환
        # paragraph=True: 문단 단위로 그룹화
        result = self.reader.readtext(
            img_array,
            detail=1,
            paragraph=False,  # 개별 텍스트 블록 유지
        )
        return result

    def _parse_result(self, result: list) -> list[OCRResult]:
        """EasyOCR 결과를 OCRResult로 변환

        EasyOCR 결과 형식:
        [
            ([[x1,y1], [x2,y2], [x3,y3], [x4,y4]], text, confidence),
            ...
        ]
        """
        ocr_results = []

        if not result:
            return ocr_results

        for item in result:
            if len(item) < 3:
                continue

            box_points = item[0]
            text = item[1]
            confidence = item[2]

            if not text or not text.strip():
                continue

            # 바운딩 박스 계산 (4점 → XYWH)
            xs = [p[0] for p in box_points]
            ys = [p[1] for p in box_points]
            x = int(min(xs))
            y = int(min(ys))
            width = int(max(xs) - x)
            height = int(max(ys) - y)

            ocr_results.append(OCRResult(
                text=text.strip(),
                confidence=float(confidence),
                bounding_box=BoundingBox(x=x, y=y, width=width, height=height),
            ))

        return ocr_results

    async def recognize(self, image: Image.Image, preprocess: bool = True) -> list[OCRResult]:
        """이미지에서 텍스트 인식

        Args:
            image: PIL Image 객체
            preprocess: OCR 전처리 적용 여부 (기본 True)

        Returns:
            인식된 텍스트 목록
        """
        # 이미지 리사이즈 (CPU 모드에서 성능 최적화)
        resized = self._resize_image(image)

        # 전처리 적용 (대비/선명도 향상)
        if preprocess:
            resized = self._preprocess_for_ocr(resized)

        img_array = self._image_to_array(resized)

        # EasyOCR은 동기 함수이므로 executor에서 실행
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self._run_ocr, img_array)

        return self._parse_result(result)

    async def recognize_region(
        self, image: Image.Image, region: BoundingBox
    ) -> OCRResult | None:
        """지정된 영역에서 텍스트 인식

        Args:
            image: PIL Image 객체
            region: 인식할 영역

        Returns:
            인식 결과 또는 None
        """
        try:
            # 영역 크롭
            cropped = image.crop((
                region.x,
                region.y,
                region.x + region.width,
                region.y + region.height,
            ))
            print(f"[EasyOCR] Cropped image: {cropped.width}x{cropped.height}")

            results = await self.recognize(cropped)
            print(f"[EasyOCR] Recognition returned {len(results) if results else 0} results")

            if not results:
                return None

            # 여러 줄이 있으면 합치기
            if len(results) == 1:
                return results[0]

            # 여러 결과를 하나로 합침 (y좌표 순서대로)
            sorted_results = sorted(
                results,
                key=lambda r: r.bounding_box.y if r.bounding_box else 0
            )
            combined_text = "\n".join(r.text for r in sorted_results)
            avg_confidence = sum(r.confidence for r in sorted_results) / len(sorted_results)

            return OCRResult(
                text=combined_text,
                confidence=avg_confidence,
                bounding_box=region,
            )
        except Exception as e:
            print(f"[EasyOCR] Error in recognize_region: {e}")
            import traceback
            traceback.print_exc()
            raise

    def _extract_by_color(
        self, image: Image.Image, color_range: str
    ) -> Image.Image:
        """색상 범위로 텍스트 추출

        Args:
            image: 원본 이미지
            color_range: 'gray' (회색/어두운 글자) 또는 'white' (흰색/밝은 글자)

        Returns:
            해당 색상만 추출된 이미지
        """
        import cv2

        img_array = np.array(image)
        img_hsv = cv2.cvtColor(img_array, cv2.COLOR_RGB2HSV)

        if color_range == 'gray':
            # 회색 글자: 채도가 낮고 밝기가 중간 (화자 이름)
            lower = np.array([0, 0, 80])
            upper = np.array([180, 50, 180])
        else:  # white
            # 흰색/밝은 글자: 채도가 낮고 밝기가 높음 (대사 본문)
            lower = np.array([0, 0, 180])
            upper = np.array([180, 50, 255])

        mask = cv2.inRange(img_hsv, lower, upper)

        # 마스크 적용 (텍스트 부분만 검정, 나머지 흰색)
        result = np.ones_like(img_array) * 255
        result[mask > 0] = [0, 0, 0]  # 텍스트를 검정으로

        return Image.fromarray(result)

    async def recognize_dialogue(
        self, image: Image.Image, region: BoundingBox
    ) -> tuple[str | None, str | None, float]:
        """대사 영역에서 화자와 대사를 색상+위치 기반으로 분리하여 인식

        명일방주 대사 영역 구조:
        - 회색 글자 + 좌측: 화자 이름
        - 흰색/밝은 글자: 대사 본문

        Args:
            image: PIL Image 객체
            region: 인식할 영역

        Returns:
            (speaker, dialogue, confidence) 튜플
        """
        try:
            # 영역 크롭
            cropped = image.crop((
                region.x,
                region.y,
                region.x + region.width,
                region.y + region.height,
            ))

            # 화자 영역 기준 (좌측 50%)
            speaker_x_threshold = cropped.width * 0.50

            # 1. 회색 글자 추출 (화자 이름)
            gray_image = self._extract_by_color(cropped, 'gray')
            gray_results = await self.recognize(gray_image)

            # 2. 흰색/밝은 글자 추출 (대사 본문)
            white_image = self._extract_by_color(cropped, 'white')
            white_results = await self.recognize(white_image)

            speaker = None
            dialogue = None
            confidences = []

            # 화자: 회색 글자 중 좌측에 있는 것
            if gray_results:
                speaker_parts = [
                    r for r in gray_results
                    if r.bounding_box and r.bounding_box.x < speaker_x_threshold
                ]
                if speaker_parts:
                    speaker = " ".join(r.text for r in speaker_parts)
                    confidences.extend(r.confidence for r in speaker_parts)

            # 대사: 흰색 글자 (y좌표 순서로 정렬)
            if white_results:
                # y좌표 순서로 정렬 후 합침
                white_results.sort(key=lambda r: r.bounding_box.y if r.bounding_box else 0)
                dialogue = " ".join(r.text for r in white_results)
                confidences.extend(r.confidence for r in white_results)

            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

            print(f"[EasyOCR] Color+Position separated - Speaker: {speaker}, Dialogue: {dialogue[:50] if dialogue else 'None'}...")

            return speaker, dialogue, avg_confidence

        except Exception as e:
            print(f"[EasyOCR] Error in recognize_dialogue: {e}")
            import traceback
            traceback.print_exc()
            raise

    async def recognize_all_text(self, image: Image.Image) -> str:
        """이미지에서 모든 텍스트를 단순 추출 (매칭용)

        화자/대사 분리 없이 전체 텍스트만 추출.
        DialogueMatcher와 함께 사용하면 스토리 데이터에서 정확한 대사를 찾음.

        Args:
            image: PIL Image 객체

        Returns:
            인식된 전체 텍스트
        """
        results = await self.recognize(image)
        if not results:
            return ""

        # y좌표 순서로 정렬 후 합침
        results.sort(key=lambda r: r.bounding_box.y if r.bounding_box else 0)
        return " ".join(r.text for r in results)

    def get_supported_languages(self) -> list[str]:
        """지원하는 언어 목록"""
        return list(self.LANGUAGE_MAP.keys())

    def set_language(self, language: str) -> None:
        """인식 언어 설정"""
        if language != self._language:
            self._language = language
            self._reader = None  # 다음 사용 시 재초기화


# 호환성을 위한 별칭
RapidOCRProvider = EasyOCRProvider
PaddleOCRProvider = EasyOCRProvider
