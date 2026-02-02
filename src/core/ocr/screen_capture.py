"""화면 캡처 모듈"""

import asyncio
from dataclasses import dataclass

import mss
import mss.tools
from PIL import Image

from ..interfaces.ocr import BoundingBox


@dataclass
class Monitor:
    """모니터 정보"""

    id: int
    left: int
    top: int
    width: int
    height: int
    name: str = ""


class ScreenCapture:
    """화면 캡처 유틸리티

    mss 라이브러리를 사용하여 빠른 화면 캡처 제공.
    게임 창 영역 또는 전체 화면 캡처 지원.
    """

    def __init__(self):
        self._sct: mss.mss | None = None

    @property
    def sct(self) -> mss.mss:
        """mss 인스턴스 (lazy loading)"""
        if self._sct is None:
            self._sct = mss.mss()
        return self._sct

    def get_monitors(self) -> list[Monitor]:
        """사용 가능한 모니터 목록"""
        monitors = []
        for i, m in enumerate(self.sct.monitors):
            if i == 0:
                # 첫 번째는 전체 가상 스크린
                name = "All Monitors"
            else:
                name = f"Monitor {i}"

            monitors.append(Monitor(
                id=i,
                left=m["left"],
                top=m["top"],
                width=m["width"],
                height=m["height"],
                name=name,
            ))
        return monitors

    def capture_monitor(self, monitor_id: int = 1) -> Image.Image:
        """모니터 전체 캡처

        Args:
            monitor_id: 모니터 ID (0=전체, 1=주 모니터, 2+=추가 모니터)

        Returns:
            캡처된 이미지
        """
        monitor = self.sct.monitors[monitor_id]
        screenshot = self.sct.grab(monitor)
        return Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

    def capture_region(self, region: BoundingBox) -> Image.Image:
        """특정 영역 캡처

        Args:
            region: 캡처할 영역

        Returns:
            캡처된 이미지
        """
        monitor = {
            "left": region.x,
            "top": region.y,
            "width": region.width,
            "height": region.height,
        }
        screenshot = self.sct.grab(monitor)
        return Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

    async def capture_monitor_async(self, monitor_id: int = 1) -> Image.Image:
        """모니터 전체 비동기 캡처"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.capture_monitor, monitor_id)

    async def capture_region_async(self, region: BoundingBox) -> Image.Image:
        """특정 영역 비동기 캡처"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.capture_region, region)

    def close(self):
        """리소스 정리"""
        if self._sct:
            self._sct.close()
            self._sct = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# 명일방주 대사 영역 프리셋 (1920x1080 기준)
DIALOGUE_REGION_PRESETS = {
    "1920x1080": BoundingBox(x=200, y=780, width=1520, height=180),
    "2560x1440": BoundingBox(x=267, y=1040, width=2027, height=240),
    "1280x720": BoundingBox(x=133, y=520, width=1013, height=120),
}


def get_dialogue_region(screen_width: int, screen_height: int) -> BoundingBox:
    """화면 해상도에 맞는 대사 영역 반환

    명일방주 대사 박스는 화면 하단 약 72-89% 영역에 위치.
    좌우 약 10% 여백.

    Args:
        screen_width: 화면 너비
        screen_height: 화면 높이

    Returns:
        대사 영역 바운딩 박스
    """
    key = f"{screen_width}x{screen_height}"
    if key in DIALOGUE_REGION_PRESETS:
        return DIALOGUE_REGION_PRESETS[key]

    # 동적 계산 (16:9 기준)
    margin_x = int(screen_width * 0.10)
    y_start = int(screen_height * 0.72)
    y_end = int(screen_height * 0.89)

    return BoundingBox(
        x=margin_x,
        y=y_start,
        width=screen_width - (margin_x * 2),
        height=y_end - y_start,
    )
