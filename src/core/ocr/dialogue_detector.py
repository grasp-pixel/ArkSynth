"""게임 대사 감지 모듈"""

import asyncio
import hashlib
from dataclasses import dataclass, field
from typing import Callable

import numpy as np
from PIL import Image

from ..interfaces.ocr import BoundingBox, OCRResult
from .easyocr_provider import EasyOCRProvider
from .screen_capture import ScreenCapture, get_dialogue_region


@dataclass
class DialogueDetection:
    """감지된 대사 정보"""

    text: str
    speaker: str | None = None
    confidence: float = 0.0
    timestamp: float = 0.0
    region: BoundingBox | None = None


@dataclass
class DetectorConfig:
    """감지기 설정"""

    # 캡처 설정
    monitor_id: int = 1
    dialogue_region: BoundingBox | None = None  # None이면 자동 계산

    # OCR 설정
    language: str = "ko"
    min_confidence: float = 0.5

    # 감지 설정
    poll_interval: float = 0.1  # 캡처 간격 (초) - 변화 감지용으로 짧게
    text_change_threshold: float = 0.8  # 텍스트 변경 감지 임계값

    # 타이핑 안정화 설정 (화면 변화 감지)
    stability_threshold: int = 3  # 연속 N번 같은 화면이면 안정화로 판단
    pixel_diff_threshold: float = 0.01  # 픽셀 변화율 임계값 (1% 미만이면 같은 화면)


class DialogueDetector:
    """실시간 대사 감지기

    화면을 주기적으로 캡처하고 OCR을 수행하여
    새로운 대사가 나타나면 콜백을 호출합니다.

    타이핑 효과 감지:
    - 화면이 계속 변하면 타이핑 중으로 판단하여 OCR 스킵
    - 화면이 안정화되면 (N번 연속 같은 화면) OCR 실행
    """

    def __init__(self, config: DetectorConfig | None = None):
        self.config = config or DetectorConfig()
        self._capture = ScreenCapture()
        self._ocr = EasyOCRProvider(language=self.config.language)
        self._running = False
        self._last_text: str = ""
        self._callbacks: list[Callable[[DialogueDetection], None]] = []

        # 타이핑 안정화 감지용
        self._last_image_hash: str = ""
        self._stability_count: int = 0
        self._last_stable_hash: str = ""  # 마지막으로 OCR 실행한 화면

    def _compute_image_hash(self, image: Image.Image) -> str:
        """이미지 해시 계산 (빠른 비교용)

        이미지를 축소하여 해시 계산 - 속도와 정확도 균형.
        """
        # 작은 크기로 축소 (빠른 비교)
        small = image.resize((64, 64), Image.Resampling.BILINEAR)
        pixels = np.array(small).tobytes()
        return hashlib.md5(pixels).hexdigest()

    def _compute_pixel_diff(self, img1: Image.Image, img2: Image.Image) -> float:
        """두 이미지의 픽셀 변화율 계산

        Returns:
            변화율 (0.0 ~ 1.0)
        """
        # 같은 크기로 축소
        size = (64, 64)
        arr1 = np.array(img1.resize(size, Image.Resampling.BILINEAR), dtype=np.float32)
        arr2 = np.array(img2.resize(size, Image.Resampling.BILINEAR), dtype=np.float32)

        # 픽셀 차이 계산
        diff = np.abs(arr1 - arr2)
        # 255 기준으로 정규화하여 변화율 계산
        change_rate = np.mean(diff) / 255.0
        return float(change_rate)

    def _check_stability(self, image: Image.Image) -> bool:
        """화면 안정화 여부 확인

        타이핑 효과 중에는 False 반환 (OCR 스킵).
        화면이 안정화되면 True 반환 (OCR 실행).

        Returns:
            True면 OCR 실행, False면 스킵
        """
        current_hash = self._compute_image_hash(image)

        # 이전 화면과 같은지 확인
        if current_hash == self._last_image_hash:
            self._stability_count += 1
        else:
            self._stability_count = 1  # 리셋 (현재 프레임이 첫 번째)
            self._last_image_hash = current_hash

        # 안정화 임계값 도달 여부
        is_stable = self._stability_count >= self.config.stability_threshold

        if is_stable:
            # 이미 OCR 실행한 화면이면 스킵
            if current_hash == self._last_stable_hash:
                return False
            self._last_stable_hash = current_hash
            print(f"[DialogueDetector] 화면 안정화됨 (count={self._stability_count})")
            return True

        return False

    def _get_dialogue_region(self) -> BoundingBox:
        """대사 영역 가져오기"""
        if self.config.dialogue_region:
            return self.config.dialogue_region

        # 모니터 해상도 기반 자동 계산
        monitors = self._capture.get_monitors()
        if self.config.monitor_id < len(monitors):
            monitor = monitors[self.config.monitor_id]
            return get_dialogue_region(monitor.width, monitor.height)

        # 기본값 (1920x1080)
        return get_dialogue_region(1920, 1080)

    async def _capture_dialogue_region(self) -> Image.Image | None:
        """대사 영역 캡처 (헬퍼)"""
        try:
            monitors = self._capture.get_monitors()
            if self.config.monitor_id >= len(monitors):
                return None

            monitor = monitors[self.config.monitor_id]
            rel_region = self._get_dialogue_region()

            # 절대 좌표로 변환
            abs_region = BoundingBox(
                x=monitor.left + rel_region.x,
                y=monitor.top + rel_region.y,
                width=rel_region.width,
                height=rel_region.height,
            )

            return await self._capture.capture_region_async(abs_region)
        except Exception as e:
            print(f"[DialogueDetector] Capture error: {e}")
            return None

    def on_dialogue(self, callback: Callable[[DialogueDetection], None]) -> None:
        """대사 감지 콜백 등록

        Args:
            callback: DialogueDetection을 받는 콜백 함수
        """
        self._callbacks.append(callback)

    def _notify_callbacks(self, detection: DialogueDetection) -> None:
        """등록된 콜백들에게 알림"""
        for callback in self._callbacks:
            try:
                callback(detection)
            except Exception as e:
                print(f"Callback error: {e}")

    def _is_text_changed(self, new_text: str) -> bool:
        """텍스트 변경 여부 확인"""
        if not self._last_text:
            return bool(new_text.strip())

        if not new_text.strip():
            return False

        # 정확히 같으면 변경 없음
        if new_text == self._last_text:
            return False

        # 유사도 계산 (간단한 레벤슈타인 비율)
        len1, len2 = len(self._last_text), len(new_text)
        if len1 == 0 or len2 == 0:
            return True

        common = len(set(self._last_text) & set(new_text))
        similarity = common / max(len1, len2)

        return similarity < self.config.text_change_threshold

    async def detect_once(self) -> DialogueDetection | None:
        """한 번 감지 수행

        Returns:
            감지된 대사 또는 None
        """
        import time

        try:
            # 모니터 정보 가져오기
            monitors = self._capture.get_monitors()
            print(f"[DialogueDetector] Found {len(monitors)} monitors, requested id={self.config.monitor_id}")

            if self.config.monitor_id >= len(monitors):
                print(f"[DialogueDetector] Monitor ID {self.config.monitor_id} out of range")
                return None

            monitor = monitors[self.config.monitor_id]
            print(f"[DialogueDetector] Using monitor: {monitor.name} ({monitor.width}x{monitor.height}) at ({monitor.left}, {monitor.top})")

            rel_region = self._get_dialogue_region()
            print(f"[DialogueDetector] Dialogue region: x={rel_region.x}, y={rel_region.y}, w={rel_region.width}, h={rel_region.height}")

            # 절대 좌표로 변환 (모니터 오프셋 적용)
            abs_region = BoundingBox(
                x=monitor.left + rel_region.x,
                y=monitor.top + rel_region.y,
                width=rel_region.width,
                height=rel_region.height,
            )
            print(f"[DialogueDetector] Absolute region: x={abs_region.x}, y={abs_region.y}")

            image = await self._capture.capture_region_async(abs_region)
            print(f"[DialogueDetector] Captured image: {image.width}x{image.height}")

            result = await self._ocr.recognize_region(image, BoundingBox(
                x=0, y=0, width=image.width, height=image.height
            ))
            print(f"[DialogueDetector] OCR result: {result}")

            if not result or result.confidence < self.config.min_confidence:
                print(f"[DialogueDetector] No result or low confidence")
                return None

            return DialogueDetection(
                text=result.text,
                confidence=result.confidence,
                timestamp=time.time(),
                region=rel_region,
            )

        except Exception as e:
            print(f"[DialogueDetector] Error in detect_once: {e}")
            import traceback
            traceback.print_exc()
            raise

    async def detect_from_image(self, image: Image.Image) -> DialogueDetection | None:
        """이미지에서 대사 감지

        Args:
            image: 분석할 이미지

        Returns:
            감지된 대사 또는 None
        """
        import time

        results = await self._ocr.recognize(image)

        if not results:
            return None

        # 가장 신뢰도 높은 결과 또는 전체 합치기
        if len(results) == 1:
            r = results[0]
            if r.confidence < self.config.min_confidence:
                return None
            return DialogueDetection(
                text=r.text,
                confidence=r.confidence,
                timestamp=time.time(),
                region=r.bounding_box,
            )

        # 여러 줄 합치기 (y좌표 순서)
        sorted_results = sorted(
            [r for r in results if r.confidence >= self.config.min_confidence],
            key=lambda r: r.bounding_box.y if r.bounding_box else 0
        )

        if not sorted_results:
            return None

        combined_text = "\n".join(r.text for r in sorted_results)
        avg_confidence = sum(r.confidence for r in sorted_results) / len(sorted_results)

        return DialogueDetection(
            text=combined_text,
            confidence=avg_confidence,
            timestamp=time.time(),
        )

    async def start_monitoring(self) -> None:
        """실시간 모니터링 시작

        타이핑 효과 감지:
        1. 빠른 간격으로 캡처 (0.1초)
        2. 화면 변화 감지 (해시 비교)
        3. 안정화되면 OCR 실행
        """
        self._running = True
        print(f"[DialogueDetector] Monitoring started (interval: {self.config.poll_interval}s, stability: {self.config.stability_threshold})")

        while self._running:
            try:
                # 캡처
                image = await self._capture_dialogue_region()
                if image is None:
                    await asyncio.sleep(self.config.poll_interval)
                    continue

                # 안정화 체크 (타이핑 중이면 스킵)
                if not self._check_stability(image):
                    await asyncio.sleep(self.config.poll_interval)
                    continue

                # OCR 실행 (안정화된 화면만)
                detection = await self.detect_from_image(image)

                if detection and self._is_text_changed(detection.text):
                    self._last_text = detection.text
                    self._notify_callbacks(detection)

            except Exception as e:
                print(f"[DialogueDetector] Error: {e}")

            await asyncio.sleep(self.config.poll_interval)

    def stop_monitoring(self) -> None:
        """모니터링 중지"""
        self._running = False
        print("[DialogueDetector] Monitoring stopped")

    def set_language(self, language: str) -> None:
        """OCR 언어 변경"""
        self._ocr.set_language(language)
        self.config.language = language

    def close(self) -> None:
        """리소스 정리"""
        self.stop_monitoring()
        self._capture.close()
