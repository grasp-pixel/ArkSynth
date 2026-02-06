"""화면 캡처 모듈"""

import asyncio
from dataclasses import dataclass
from enum import Enum

import mss
import mss.tools
from PIL import Image

from ..interfaces.ocr import BoundingBox


class OCRRegionType(Enum):
    """OCR 영역 타입"""

    DIALOGUE = "dialogue"  # 하단 대사 영역
    SUBTITLE = "subtitle"  # 화면 중앙 자막 영역

# Windows 전용 모듈 (조건부 임포트)
try:
    import win32gui
    import win32ui
    import win32con
    import win32api
    import ctypes
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False


@dataclass
class Monitor:
    """모니터 정보"""

    id: int
    left: int
    top: int
    width: int
    height: int
    name: str = ""


@dataclass
class WindowInfo:
    """윈도우 정보"""

    hwnd: int  # 윈도우 핸들
    title: str  # 창 제목
    left: int
    top: int
    width: int
    height: int
    process_name: str = ""


class ScreenCapture:
    """화면 캡처 유틸리티

    mss 라이브러리를 사용하여 빠른 화면 캡처 제공.
    게임 창 영역 또는 전체 화면 캡처 지원.

    Note: mss는 thread-local storage를 사용하므로 async 환경에서는
    각 캡처마다 새 인스턴스를 생성해야 합니다.
    """

    def get_monitors(self) -> list[Monitor]:
        """사용 가능한 모니터 목록"""
        monitors = []
        with mss.mss() as sct:
            for i, m in enumerate(sct.monitors):
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
        with mss.mss() as sct:
            monitor = sct.monitors[monitor_id]
            screenshot = sct.grab(monitor)
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
        with mss.mss() as sct:
            screenshot = sct.grab(monitor)
            return Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

    async def capture_monitor_async(self, monitor_id: int = 1) -> Image.Image:
        """모니터 전체 비동기 캡처"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.capture_monitor, monitor_id)

    async def capture_region_async(self, region: BoundingBox) -> Image.Image:
        """특정 영역 비동기 캡처"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.capture_region, region)

    def get_windows(self) -> list[WindowInfo]:
        """표시된 윈도우 목록 가져오기 (Windows 전용)

        Returns:
            WindowInfo 목록 (타이틀이 있는 표시된 창들)
        """
        if not HAS_WIN32:
            print("[ScreenCapture] win32 모듈 없음")
            return []

        windows = []
        error_count = 0

        def enum_callback(hwnd, _):
            nonlocal error_count
            try:
                if not win32gui.IsWindowVisible(hwnd):
                    return True
                title = win32gui.GetWindowText(hwnd)
                if not title:
                    return True

                rect = win32gui.GetWindowRect(hwnd)
                left, top, right, bottom = rect
                width = right - left
                height = bottom - top

                # 최소 크기 필터 (너무 작은 창 제외)
                if width < 100 or height < 100:
                    return True

                windows.append(WindowInfo(
                    hwnd=hwnd,
                    title=title,
                    left=left,
                    top=top,
                    width=width,
                    height=height,
                ))
            except Exception as e:
                error_count += 1
                if error_count <= 3:  # 처음 3개 에러만 출력
                    print(f"[ScreenCapture] 윈도우 열거 오류: {e}")
            return True

        try:
            win32gui.EnumWindows(enum_callback, None)
            print(f"[ScreenCapture] 윈도우 {len(windows)}개 발견 (오류: {error_count}개)")
        except Exception as e:
            print(f"[ScreenCapture] EnumWindows 실패: {e}")
            import traceback
            traceback.print_exc()

        return windows

    def capture_window(self, hwnd: int) -> Image.Image | None:
        """특정 윈도우 캡처 (Windows 전용)

        Args:
            hwnd: 윈도우 핸들

        Returns:
            캡처된 이미지 또는 None
        """
        if not HAS_WIN32:
            return None

        try:
            # 창 크기 가져오기
            rect = win32gui.GetWindowRect(hwnd)
            left, top, right, bottom = rect
            width = right - left
            height = bottom - top

            if width <= 0 or height <= 0:
                return None

            # 윈도우 DC 가져오기
            hwnd_dc = win32gui.GetWindowDC(hwnd)
            mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
            save_dc = mfc_dc.CreateCompatibleDC()

            # 비트맵 생성
            bitmap = win32ui.CreateBitmap()
            bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
            save_dc.SelectObject(bitmap)

            # 창 내용 복사 (PrintWindow 사용 - 가려진 창도 캡처 가능)
            # ctypes로 직접 호출 (pywin32 버전 호환성)
            PW_RENDERFULLCONTENT = 2
            try:
                result = ctypes.windll.user32.PrintWindow(
                    hwnd, save_dc.GetSafeHdc(), PW_RENDERFULLCONTENT
                )
            except Exception:
                result = 0

            if result == 0:
                # PrintWindow 실패 시 BitBlt 시도
                save_dc.BitBlt((0, 0), (width, height), mfc_dc, (0, 0), win32con.SRCCOPY)

            # 비트맵 데이터 추출
            bmp_info = bitmap.GetInfo()
            bmp_str = bitmap.GetBitmapBits(True)

            # PIL Image로 변환
            image = Image.frombuffer(
                'RGB',
                (bmp_info['bmWidth'], bmp_info['bmHeight']),
                bmp_str, 'raw', 'BGRX', 0, 1
            )

            # 리소스 정리
            win32gui.DeleteObject(bitmap.GetHandle())
            save_dc.DeleteDC()
            mfc_dc.DeleteDC()
            win32gui.ReleaseDC(hwnd, hwnd_dc)

            return image

        except Exception as e:
            print(f"[ScreenCapture] Window capture error: {e}")
            return None

    async def get_windows_async(self) -> list[WindowInfo]:
        """윈도우 목록 비동기 가져오기"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.get_windows)

    async def capture_window_async(self, hwnd: int) -> Image.Image | None:
        """윈도우 비동기 캡처"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.capture_window, hwnd)

    def close(self):
        """리소스 정리 (호환성 유지)"""
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


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
    margin_x = int(screen_width * 0.01)  # 좌우 1% 여백
    y_start = int(screen_height * 0.80)  # 하단 80%부터
    y_end = screen_height                # 하단 끝까지

    return BoundingBox(
        x=margin_x,
        y=y_start,
        width=screen_width - (margin_x * 2),
        height=y_end - y_start,
    )


def get_subtitle_region(screen_width: int, screen_height: int) -> BoundingBox:
    """화면 중앙 자막 영역 반환

    자막은 화면 중앙 (상단 40% ~ 70%) 영역에 표시.
    상단 헤더(~15%)를 고려하여 아래로 이동.
    좌우 1% 여백.

    Args:
        screen_width: 화면 너비
        screen_height: 화면 높이

    Returns:
        자막 영역 바운딩 박스
    """
    margin_x = int(screen_width * 0.01)  # 좌우 1% 여백
    y_start = int(screen_height * 0.40)  # 상단 40%부터 (헤더 15% 감안)
    y_end = int(screen_height * 0.70)    # 70%까지

    return BoundingBox(
        x=margin_x,
        y=y_start,
        width=screen_width - (margin_x * 2),
        height=y_end - y_start,
    )


def get_region_by_type(
    region_type: OCRRegionType, screen_width: int, screen_height: int
) -> BoundingBox:
    """영역 타입에 따른 바운딩 박스 반환"""
    if region_type == OCRRegionType.DIALOGUE:
        return get_dialogue_region(screen_width, screen_height)
    elif region_type == OCRRegionType.SUBTITLE:
        return get_subtitle_region(screen_width, screen_height)
    else:
        raise ValueError(f"Unknown region type: {region_type}")
