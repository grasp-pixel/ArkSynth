"""게임 대사 감지 모듈"""

import asyncio
from dataclasses import dataclass, field
from typing import Callable

from PIL import Image

from ..interfaces.ocr import BoundingBox, OCRResult
from .paddle_ocr import PaddleOCRProvider
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
    poll_interval: float = 0.5  # 초 단위
    text_change_threshold: float = 0.8  # 텍스트 변경 감지 임계값


class DialogueDetector:
    """실시간 대사 감지기

    화면을 주기적으로 캡처하고 OCR을 수행하여
    새로운 대사가 나타나면 콜백을 호출합니다.
    """

    def __init__(self, config: DetectorConfig | None = None):
        self.config = config or DetectorConfig()
        self._capture = ScreenCapture()
        self._ocr = PaddleOCRProvider(language=self.config.language)
        self._running = False
        self._last_text: str = ""
        self._callbacks: list[Callable[[DialogueDetection], None]] = []

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

        region = self._get_dialogue_region()
        image = await self._capture.capture_region_async(region)
        result = await self._ocr.recognize_region(image, BoundingBox(
            x=0, y=0, width=image.width, height=image.height
        ))

        if not result or result.confidence < self.config.min_confidence:
            return None

        return DialogueDetection(
            text=result.text,
            confidence=result.confidence,
            timestamp=time.time(),
            region=region,
        )

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
        """실시간 모니터링 시작"""
        self._running = True
        print(f"[DialogueDetector] Monitoring started (interval: {self.config.poll_interval}s)")

        while self._running:
            try:
                detection = await self.detect_once()

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
