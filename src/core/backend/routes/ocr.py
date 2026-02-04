"""OCR API 라우트"""

import base64
import io
import time
from typing import Annotated

from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from fastapi.responses import Response
from pydantic import BaseModel
from PIL import Image

from .episodes import get_loader, DialogueInfo
from .. import gpu_semaphore_context

router = APIRouter()

# 캡처된 이미지 캐시 (간단한 메모리 캐시)
_capture_cache: dict[str, tuple[bytes, float]] = {}
_CACHE_TTL = 30.0  # 30초


# --- 응답 모델 ---


class BoundingBoxResponse(BaseModel):
    x: int
    y: int
    width: int
    height: int


class OCRResultResponse(BaseModel):
    text: str
    confidence: float
    bounding_box: BoundingBoxResponse | None = None


class RecognizeResponse(BaseModel):
    results: list[OCRResultResponse]
    language: str


class ScreenCaptureResponse(BaseModel):
    image_base64: str
    width: int
    height: int


class MonitorInfo(BaseModel):
    id: int
    name: str
    left: int
    top: int
    width: int
    height: int


class MonitorsResponse(BaseModel):
    monitors: list[MonitorInfo]


class DialogueRegionResponse(BaseModel):
    region: BoundingBoxResponse
    screen_width: int
    screen_height: int


class DetectDialogueResponse(BaseModel):
    text: str | None
    confidence: float
    timestamp: float


class WindowInfoResponse(BaseModel):
    hwnd: int
    title: str
    left: int
    top: int
    width: int
    height: int


class WindowsResponse(BaseModel):
    windows: list[WindowInfoResponse]


# --- 엔드포인트 ---


@router.get("/monitors", response_model=MonitorsResponse)
async def list_monitors():
    """사용 가능한 모니터 목록"""
    try:
        from ...ocr import ScreenCapture

        with ScreenCapture() as capture:
            monitors = capture.get_monitors()

        return MonitorsResponse(
            monitors=[
                MonitorInfo(
                    id=m.id,
                    name=m.name,
                    left=m.left,
                    top=m.top,
                    width=m.width,
                    height=m.height,
                )
                for m in monitors
            ]
        )
    except ImportError:
        raise HTTPException(status_code=501, detail="OCR module not available")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/windows", response_model=WindowsResponse)
async def list_windows():
    """표시된 윈도우 목록 (Windows 전용)"""
    try:
        from ...ocr import ScreenCapture

        capture = ScreenCapture()
        windows = await capture.get_windows_async()
        capture.close()

        return WindowsResponse(
            windows=[
                WindowInfoResponse(
                    hwnd=w.hwnd,
                    title=w.title,
                    left=w.left,
                    top=w.top,
                    width=w.width,
                    height=w.height,
                )
                for w in windows
            ]
        )
    except ImportError:
        raise HTTPException(status_code=501, detail="OCR module not available")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/capture/window/image")
async def capture_window_image(
    hwnd: Annotated[int, Query(description="윈도우 핸들")],
    ignore_top_ratio: Annotated[float, Query(description="상단 무시 비율")] = 0.0,
):
    """특정 윈도우 캡처 - 직접 JPEG 이미지 반환 (Windows 전용)"""
    try:
        from ...ocr import ScreenCapture

        capture = ScreenCapture()
        image = await capture.capture_window_async(hwnd)
        capture.close()

        if image is None:
            raise HTTPException(status_code=400, detail="Failed to capture window")

        # 상단 UI 영역 제외
        if ignore_top_ratio > 0:
            top_margin = int(image.height * ignore_top_ratio)
            image = image.crop(
                (
                    0,
                    top_margin,
                    image.width,
                    image.height,
                )
            )

        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=85)
        buffer.seek(0)
        image_bytes = buffer.read()

        return Response(
            content=image_bytes,
            media_type="image/jpeg",
            headers={"Cache-Control": "no-cache"},
        )
    except ImportError:
        raise HTTPException(status_code=501, detail="OCR module not available")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/detect/window", response_model=DetectDialogueResponse)
async def detect_window_dialogue(
    hwnd: Annotated[int, Query(description="윈도우 핸들")],
    lang: Annotated[str, Query(description="OCR 언어")] = "ko",
    min_confidence: Annotated[float, Query(description="최소 신뢰도")] = 0.2,
    ignore_top_ratio: Annotated[
        float, Query(description="상단 무시 비율 (UI 제외)")
    ] = 0.15,
):
    """윈도우에서 대사 감지 (캡처 + OCR)"""
    import traceback

    total_start = time.time()
    print(f"[OCR-API] detect_window_dialogue 시작: hwnd={hwnd}, lang={lang}")

    try:
        from ...ocr import ScreenCapture, EasyOCRProvider

        # 1. 캡처
        capture_start = time.time()
        capture = ScreenCapture()
        image = await capture.capture_window_async(hwnd)
        capture.close()
        print(f"[OCR-API] 캡처 완료: {time.time() - capture_start:.2f}초")

        if image is None:
            print(f"[OCR-API] 캡처 실패: hwnd={hwnd}")
            raise HTTPException(status_code=400, detail="Failed to capture window")

        print(f"[OCR-API] 캡처 이미지: {image.width}x{image.height}")

        # 상단 UI 영역 제외 (LOG, AUTO, SKIP 등)
        if ignore_top_ratio > 0:
            top_margin = int(image.height * ignore_top_ratio)
            image = image.crop(
                (
                    0,
                    top_margin,
                    image.width,
                    image.height,
                )
            )
            print(
                f"[OCR-API] 상단 {ignore_top_ratio * 100:.0f}% 제외 후: {image.width}x{image.height}"
            )

        # 2. OCR
        ocr_start = time.time()
        ocr = EasyOCRProvider(language=lang)
        results = await ocr.recognize(image)
        print(f"[OCR-API] OCR 완료: {time.time() - ocr_start:.2f}초")

        if results:
            # 디버깅: 모든 OCR 결과 출력
            print(f"[OCR] Raw results ({len(results)} items):")
            for i, r in enumerate(results):
                bbox = r.bounding_box
                pos = f"({bbox.x}, {bbox.y})" if bbox else "?"
                print(f"  [{i}] conf={r.confidence:.2f} pos={pos} text='{r.text}'")

            # 모든 결과를 y좌표 순으로 정렬하여 합치기
            sorted_results = sorted(
                [r for r in results if r.confidence >= min_confidence],
                key=lambda r: r.bounding_box.y if r.bounding_box else 0,
            )

            # 디버깅: 필터링 후 결과
            filtered_count = len(results) - len(sorted_results)
            if filtered_count > 0:
                print(
                    f"[OCR] Filtered out {filtered_count} results (confidence < {min_confidence})"
                )

            if sorted_results:
                combined_text = "\n".join(r.text for r in sorted_results)
                avg_confidence = sum(r.confidence for r in sorted_results) / len(
                    sorted_results
                )
                total_elapsed = time.time() - total_start
                print(
                    f"[OCR-API] 완료: '{combined_text[:50]}...' (총 {total_elapsed:.2f}초)"
                )
                return DetectDialogueResponse(
                    text=combined_text,
                    confidence=avg_confidence,
                    timestamp=time.time(),
                )

        total_elapsed = time.time() - total_start
        print(f"[OCR-API] 완료: 텍스트 없음 (총 {total_elapsed:.2f}초)")
        return DetectDialogueResponse(
            text=None,
            confidence=0.0,
            timestamp=time.time(),
        )
    except ImportError as e:
        print(f"[OCR-API] ImportError: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=501, detail=f"OCR module not available: {e}")
    except HTTPException:
        raise
    except Exception as e:
        print(f"[OCR-API] 에러: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# --- 윈도우 안정화 감지 상태 캐시 ---
import hashlib
import numpy as np
from dataclasses import dataclass, field


@dataclass
class WindowStabilityState:
    """윈도우별 안정화 상태"""

    last_image_hash: str = ""
    stability_count: int = 0
    last_stable_hash: str = ""
    last_text: str = ""


# 윈도우별 안정화 상태 캐시
_window_stability: dict[int, WindowStabilityState] = {}


def _compute_image_hash(image) -> str:
    """이미지 해시 계산 (빠른 비교용)"""
    from PIL import Image

    small = image.resize((64, 64), Image.Resampling.BILINEAR)
    pixels = np.array(small).tobytes()
    return hashlib.md5(pixels).hexdigest()


class StableDetectResponse(BaseModel):
    text: str | None
    confidence: float
    timestamp: float
    is_stable: bool  # 화면이 안정화되었는지
    is_new: bool  # 새로운 대사인지


@router.get("/detect/window/stable", response_model=StableDetectResponse)
async def detect_window_dialogue_stable(
    hwnd: Annotated[int, Query(description="윈도우 핸들")],
    lang: Annotated[str, Query(description="OCR 언어")] = "ko",
    min_confidence: Annotated[float, Query(description="최소 신뢰도")] = 0.2,
    ignore_top_ratio: Annotated[float, Query(description="상단 무시 비율")] = 0.15,
    stability_threshold: Annotated[int, Query(description="안정화 판단 횟수")] = 3,
):
    """윈도우에서 대사 감지 - 타이핑 안정화 적용

    화면이 안정화될 때만 OCR을 수행합니다.
    타이핑 효과 중에는 is_stable=False를 반환합니다.
    """
    import traceback

    global _window_stability

    try:
        from ...ocr import ScreenCapture, EasyOCRProvider

        # 윈도우 상태 가져오기
        if hwnd not in _window_stability:
            _window_stability[hwnd] = WindowStabilityState()
        state = _window_stability[hwnd]

        # 캡처
        capture = ScreenCapture()
        image = await capture.capture_window_async(hwnd)
        capture.close()

        if image is None:
            raise HTTPException(status_code=400, detail="Failed to capture window")

        # 상단 UI 영역 제외
        if ignore_top_ratio > 0:
            top_margin = int(image.height * ignore_top_ratio)
            image = image.crop(
                (
                    0,
                    top_margin,
                    image.width,
                    image.height,
                )
            )

        # 안정화 체크
        current_hash = _compute_image_hash(image)

        if current_hash == state.last_image_hash:
            state.stability_count += 1
        else:
            state.stability_count = 1
            state.last_image_hash = current_hash

        is_stable = state.stability_count >= stability_threshold

        # 안정화되지 않음 - OCR 스킵
        if not is_stable:
            return StableDetectResponse(
                text=None,
                confidence=0.0,
                timestamp=time.time(),
                is_stable=False,
                is_new=False,
            )

        # 이미 OCR 실행한 화면 - 스킵
        if current_hash == state.last_stable_hash:
            return StableDetectResponse(
                text=state.last_text if state.last_text else None,
                confidence=0.0,
                timestamp=time.time(),
                is_stable=True,
                is_new=False,
            )

        state.last_stable_hash = current_hash

        # OCR 실행
        ocr = EasyOCRProvider(language=lang)
        results = await ocr.recognize(image)

        if results:
            sorted_results = sorted(
                [r for r in results if r.confidence >= min_confidence],
                key=lambda r: r.bounding_box.y if r.bounding_box else 0,
            )
            if sorted_results:
                combined_text = "\n".join(r.text for r in sorted_results)
                avg_confidence = sum(r.confidence for r in sorted_results) / len(
                    sorted_results
                )

                # 새로운 대사인지 확인
                is_new = combined_text != state.last_text
                state.last_text = combined_text

                return StableDetectResponse(
                    text=combined_text,
                    confidence=avg_confidence,
                    timestamp=time.time(),
                    is_stable=True,
                    is_new=is_new,
                )

        return StableDetectResponse(
            text=None,
            confidence=0.0,
            timestamp=time.time(),
            is_stable=True,
            is_new=False,
        )

    except ImportError as e:
        print(f"[OCR] ImportError: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=501, detail=f"OCR module not available: {e}")
    except HTTPException:
        raise
    except Exception as e:
        print(f"[OCR] Error in detect_window_dialogue_stable: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/detect/window/reset")
async def reset_window_stability(hwnd: int | None = None):
    """윈도우 안정화 상태 초기화"""
    global _window_stability
    if hwnd is not None:
        if hwnd in _window_stability:
            del _window_stability[hwnd]
        return {"reset": True, "hwnd": hwnd}
    else:
        _window_stability.clear()
        return {"reset": True, "message": "All window states cleared"}


@router.get("/dialogue-region", response_model=DialogueRegionResponse)
async def get_dialogue_region_endpoint(
    width: Annotated[int, Query(description="화면 너비")] = 1920,
    height: Annotated[int, Query(description="화면 높이")] = 1080,
):
    """대사 영역 좌표 계산"""
    try:
        from ...ocr import get_dialogue_region

        region = get_dialogue_region(width, height)
        return DialogueRegionResponse(
            region=BoundingBoxResponse(
                x=region.x,
                y=region.y,
                width=region.width,
                height=region.height,
            ),
            screen_width=width,
            screen_height=height,
        )
    except ImportError:
        raise HTTPException(status_code=501, detail="OCR module not available")


@router.post("/recognize", response_model=RecognizeResponse)
async def recognize_image(
    file: Annotated[UploadFile, File(description="이미지 파일")],
    lang: Annotated[str, Query(description="OCR 언어")] = "ko",
):
    """업로드된 이미지에서 텍스트 인식"""
    try:
        from ...ocr import PaddleOCRProvider

        # 이미지 로드
        contents = await file.read()
        image = Image.open(io.BytesIO(contents))

        # OCR 수행
        ocr = PaddleOCRProvider(language=lang)
        results = await ocr.recognize(image)

        return RecognizeResponse(
            results=[
                OCRResultResponse(
                    text=r.text,
                    confidence=r.confidence,
                    bounding_box=BoundingBoxResponse(
                        x=r.bounding_box.x,
                        y=r.bounding_box.y,
                        width=r.bounding_box.width,
                        height=r.bounding_box.height,
                    )
                    if r.bounding_box
                    else None,
                )
                for r in results
            ],
            language=lang,
        )
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="OCR module not available. Install with: uv pip install paddlepaddle paddleocr",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/capture", response_model=ScreenCaptureResponse)
async def capture_screen(
    monitor: Annotated[int, Query(description="모니터 ID (0=전체, 1=주 모니터)")] = 1,
):
    """화면 캡처"""
    try:
        from ...ocr import ScreenCapture

        capture = ScreenCapture()
        image = await capture.capture_monitor_async(monitor)
        capture.close()

        # Base64 인코딩 (JPEG로 압축하여 크기 축소)
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=85)
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.read()).decode("utf-8")

        return ScreenCaptureResponse(
            image_base64=image_base64,
            width=image.width,
            height=image.height,
        )
    except ImportError:
        raise HTTPException(status_code=501, detail="OCR module not available")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/capture/dialogue", response_model=ScreenCaptureResponse)
async def capture_dialogue_region(
    monitor: Annotated[int, Query(description="모니터 ID")] = 1,
):
    """대사 영역만 캡처"""
    try:
        from ...ocr import ScreenCapture, get_dialogue_region

        capture = ScreenCapture()
        monitors = capture.get_monitors()

        if monitor >= len(monitors):
            raise HTTPException(
                status_code=400, detail=f"Invalid monitor ID: {monitor}"
            )

        mon = monitors[monitor]
        region = get_dialogue_region(mon.width, mon.height)

        # 모니터 오프셋 적용
        from ...interfaces.ocr import BoundingBox

        abs_region = BoundingBox(
            x=mon.left + region.x,
            y=mon.top + region.y,
            width=region.width,
            height=region.height,
        )

        image = await capture.capture_region_async(abs_region)
        capture.close()

        # Base64 인코딩 (JPEG로 압축하여 크기 축소)
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=85)
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.read()).decode("utf-8")

        return ScreenCaptureResponse(
            image_base64=image_base64,
            width=image.width,
            height=image.height,
        )
    except ImportError:
        raise HTTPException(status_code=501, detail="OCR module not available")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/detect", response_model=DetectDialogueResponse)
async def detect_dialogue(
    monitor: Annotated[int, Query(description="모니터 ID")] = 1,
    lang: Annotated[str, Query(description="OCR 언어")] = "ko",
    min_confidence: Annotated[float, Query(description="최소 신뢰도")] = 0.2,
):
    """화면에서 대사 감지 (캡처 + OCR)"""
    import time
    import traceback

    try:
        from ...ocr import DialogueDetector, DetectorConfig

        config = DetectorConfig(
            monitor_id=monitor,
            language=lang,
            min_confidence=min_confidence,
        )
        detector = DialogueDetector(config)

        result = await detector.detect_once()
        detector.close()

        if result:
            return DetectDialogueResponse(
                text=result.text,
                confidence=result.confidence,
                timestamp=result.timestamp,
            )
        else:
            return DetectDialogueResponse(
                text=None,
                confidence=0.0,
                timestamp=time.time(),
            )
    except ImportError as e:
        print(f"[OCR] ImportError: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=501, detail=f"OCR module not available: {e}")
    except Exception as e:
        print(f"[OCR] Error in detect_dialogue: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/languages")
async def list_supported_languages():
    """지원하는 OCR 언어 목록"""
    return {
        "languages": [
            {"code": "ko", "name": "한국어"},
            {"code": "zh", "name": "中文"},
            {"code": "ja", "name": "日本語"},
            {"code": "en", "name": "English"},
        ]
    }


# --- 직접 이미지 서빙 엔드포인트 ---


@router.get("/capture/image")
async def capture_screen_image(
    monitor: Annotated[int, Query(description="모니터 ID (0=전체, 1=주 모니터)")] = 1,
):
    """화면 캡처 - 직접 JPEG 이미지 반환"""
    try:
        from ...ocr import ScreenCapture

        capture = ScreenCapture()
        image = await capture.capture_monitor_async(monitor)
        capture.close()

        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=85)
        buffer.seek(0)
        image_bytes = buffer.read()

        # 캐시 저장
        cache_key = f"monitor_{monitor}"
        _capture_cache[cache_key] = (image_bytes, time.time())

        return Response(
            content=image_bytes,
            media_type="image/jpeg",
            headers={"Cache-Control": "no-cache"},
        )
    except ImportError:
        raise HTTPException(status_code=501, detail="OCR module not available")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/capture/dialogue/image")
async def capture_dialogue_image(
    monitor: Annotated[int, Query(description="모니터 ID")] = 1,
):
    """대사 영역만 캡처 - 직접 JPEG 이미지 반환"""
    try:
        from ...ocr import ScreenCapture, get_dialogue_region
        from ...interfaces.ocr import BoundingBox

        capture = ScreenCapture()
        monitors = capture.get_monitors()

        if monitor >= len(monitors):
            raise HTTPException(
                status_code=400, detail=f"Invalid monitor ID: {monitor}"
            )

        mon = monitors[monitor]
        region = get_dialogue_region(mon.width, mon.height)

        abs_region = BoundingBox(
            x=mon.left + region.x,
            y=mon.top + region.y,
            width=region.width,
            height=region.height,
        )

        image = await capture.capture_region_async(abs_region)
        capture.close()

        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=85)
        buffer.seek(0)
        image_bytes = buffer.read()

        return Response(
            content=image_bytes,
            media_type="image/jpeg",
            headers={"Cache-Control": "no-cache"},
        )
    except ImportError:
        raise HTTPException(status_code=501, detail="OCR module not available")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/capture/region/image")
async def capture_custom_region_image(
    x: Annotated[int, Query(description="X 좌표")],
    y: Annotated[int, Query(description="Y 좌표")],
    width: Annotated[int, Query(description="너비")],
    height: Annotated[int, Query(description="높이")],
):
    """사용자 지정 영역 캡처 - 직접 JPEG 이미지 반환"""
    try:
        from ...ocr import ScreenCapture
        from ...interfaces.ocr import BoundingBox

        capture = ScreenCapture()
        region = BoundingBox(x=x, y=y, width=width, height=height)
        image = await capture.capture_region_async(region)
        capture.close()

        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=85)
        buffer.seek(0)
        image_bytes = buffer.read()

        return Response(
            content=image_bytes,
            media_type="image/jpeg",
            headers={"Cache-Control": "no-cache"},
        )
    except ImportError:
        raise HTTPException(status_code=501, detail="OCR module not available")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class CustomRegionRequest(BaseModel):
    x: int
    y: int
    width: int
    height: int


class CustomRegionResponse(BaseModel):
    saved: bool
    region: BoundingBoxResponse


# 사용자 지정 영역 저장
_custom_region: CustomRegionRequest | None = None


@router.post("/region/custom", response_model=CustomRegionResponse)
async def set_custom_region(region: CustomRegionRequest):
    """사용자 지정 캡처 영역 설정"""
    global _custom_region
    _custom_region = region
    return CustomRegionResponse(
        saved=True,
        region=BoundingBoxResponse(
            x=region.x,
            y=region.y,
            width=region.width,
            height=region.height,
        ),
    )


@router.get("/region/custom")
async def get_custom_region():
    """저장된 사용자 지정 영역 조회"""
    if _custom_region is None:
        return {"region": None}
    return {
        "region": {
            "x": _custom_region.x,
            "y": _custom_region.y,
            "width": _custom_region.width,
            "height": _custom_region.height,
        }
    }


@router.get("/detect/custom", response_model=DetectDialogueResponse)
async def detect_custom_region(
    lang: Annotated[str, Query(description="OCR 언어")] = "ko",
    min_confidence: Annotated[float, Query(description="최소 신뢰도")] = 0.5,
):
    """사용자 지정 영역에서 텍스트 감지"""
    if _custom_region is None:
        raise HTTPException(
            status_code=400,
            detail="Custom region not set. Call POST /region/custom first.",
        )

    try:
        from ...ocr import ScreenCapture, PaddleOCRProvider
        from ...interfaces.ocr import BoundingBox

        capture = ScreenCapture()
        region = BoundingBox(
            x=_custom_region.x,
            y=_custom_region.y,
            width=_custom_region.width,
            height=_custom_region.height,
        )
        image = await capture.capture_region_async(region)
        capture.close()

        ocr = PaddleOCRProvider(language=lang)
        results = await ocr.recognize(image)

        if results:
            best = max(results, key=lambda r: r.confidence)
            if best.confidence >= min_confidence:
                return DetectDialogueResponse(
                    text=best.text,
                    confidence=best.confidence,
                    timestamp=time.time(),
                )

        return DetectDialogueResponse(
            text=None,
            confidence=0.0,
            timestamp=time.time(),
        )
    except ImportError:
        raise HTTPException(status_code=501, detail="OCR module not available")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- DialogueMatcher 연동 ---


class MatchDialogueRequest(BaseModel):
    episode_id: str
    text: str
    min_similarity: float = 0.5


class MatchDialogueResponse(BaseModel):
    matched: bool
    dialogue: DialogueInfo | None = None
    similarity: float = 0.0
    index: int = -1


# DialogueMatcher 인스턴스 캐시 (에피소드별)
_matcher_cache: dict[str, "DialogueMatcher"] = {}


@router.post("/match", response_model=MatchDialogueResponse)
async def match_dialogue(request: MatchDialogueRequest):
    """OCR 텍스트를 에피소드 대사와 매칭

    Args:
        episode_id: 에피소드 ID
        text: OCR로 인식된 텍스트
        min_similarity: 최소 유사도 (기본 0.5)

    Returns:
        매칭된 대사 정보 또는 None
    """
    from ...ocr import DialogueMatcher
    from ...models.story import Dialogue

    global _matcher_cache

    try:
        # 에피소드 로드
        loader = get_loader()
        episode = loader.load_episode(request.episode_id)

        if episode is None:
            raise HTTPException(
                status_code=404, detail=f"Episode not found: {request.episode_id}"
            )

        # DialogueMatcher 가져오기 (캐시 또는 새로 생성)
        if request.episode_id not in _matcher_cache:
            _matcher_cache[request.episode_id] = DialogueMatcher(episode.dialogues)
        matcher = _matcher_cache[request.episode_id]

        # 매칭 수행
        result = matcher.find_best_match(
            request.text,
            min_similarity=request.min_similarity,
        )

        if result:
            return MatchDialogueResponse(
                matched=True,
                dialogue=DialogueInfo(
                    id=result.dialogue.id,
                    speaker_id=result.dialogue.speaker_id,
                    speaker_name=result.dialogue.speaker_name,
                    text=result.dialogue.text,
                    line_number=result.dialogue.line_number,
                ),
                similarity=result.similarity,
                index=result.index,
            )

        return MatchDialogueResponse(matched=False)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/match/reset")
async def reset_matcher(episode_id: str | None = None):
    """DialogueMatcher 상태 초기화

    Args:
        episode_id: 초기화할 에피소드 ID (None이면 전체 초기화)
    """
    global _matcher_cache

    if episode_id:
        if episode_id in _matcher_cache:
            _matcher_cache[episode_id].reset()
            return {"reset": True, "episode_id": episode_id}
        return {"reset": False, "message": "Matcher not found"}
    else:
        _matcher_cache.clear()
        return {"reset": True, "message": "All matchers cleared"}


# --- SSE 스트리밍 ---

import asyncio
import json
from sse_starlette.sse import EventSourceResponse


class DialogueStreamEvent(BaseModel):
    type: str  # "dialogue", "error", "status"
    text: str | None = None
    confidence: float = 0.0
    timestamp: float = 0.0
    is_new: bool = False


@router.get("/stream/window")
async def stream_window_dialogue(
    hwnd: Annotated[int, Query(description="윈도우 핸들")],
    lang: Annotated[str, Query(description="OCR 언어")] = "ko",
    min_confidence: Annotated[float, Query(description="최소 신뢰도")] = 0.2,
    ignore_top_ratio: Annotated[float, Query(description="상단 무시 비율")] = 0.15,
    poll_interval: Annotated[float, Query(description="폴링 간격 (초)")] = 0.3,
    stability_threshold: Annotated[int, Query(description="안정화 임계값")] = 3,
):
    """윈도우 대사 감지 SSE 스트림

    새로운 대사가 감지될 때만 이벤트를 전송합니다.
    타이핑 효과가 끝난 후 안정화된 텍스트만 전송합니다.
    """
    import traceback

    async def event_generator():
        import sys

        global _window_stability

        print(f"[SSE] 스트림 시작: hwnd={hwnd}, lang={lang}", flush=True)

        # 상태 초기화
        if hwnd not in _window_stability:
            _window_stability[hwnd] = WindowStabilityState()
        state = _window_stability[hwnd]

        try:
            from ...ocr import ScreenCapture, EasyOCRProvider

            capture = ScreenCapture()
            ocr = EasyOCRProvider(language=lang)
            print(f"[SSE] OCR Provider 초기화 완료 (하이브리드 모드)", flush=True)

            # 연결 성공 알림
            yield {
                "event": "status",
                "data": json.dumps({"type": "connected", "hwnd": hwnd}),
            }

            # 하이브리드 모드 설정
            FORCE_OCR_INTERVAL = 1.0  # 1초마다 강제 OCR (이펙트 내성)
            last_ocr_time = 0.0
            heartbeat_counter = 0
            loop_count = 0

            while True:
                loop_count += 1
                current_time = time.time()

                # 주기적 heartbeat (10번마다 = 3초마다)
                heartbeat_counter += 1
                if heartbeat_counter >= 10:
                    heartbeat_counter = 0
                    print(f"[SSE] Heartbeat #{loop_count // 10}", flush=True)
                    yield {
                        "event": "heartbeat",
                        "data": json.dumps({"timestamp": time.time()}),
                    }
                try:
                    # 캡처
                    image = await capture.capture_window_async(hwnd)
                    if image is None:
                        print(f"[SSE] 캡처 실패", flush=True)
                        yield {
                            "event": "error",
                            "data": json.dumps(
                                {
                                    "type": "capture_failed",
                                    "message": "Window capture failed",
                                }
                            ),
                        }
                        await asyncio.sleep(poll_interval * 2)
                        continue

                    # 상단 UI 영역 제외
                    if ignore_top_ratio > 0:
                        top_margin = int(image.height * ignore_top_ratio)
                        image = image.crop((0, top_margin, image.width, image.height))

                    # 안정화 체크
                    current_hash = _compute_image_hash(image)

                    if current_hash == state.last_image_hash:
                        state.stability_count += 1
                    else:
                        state.stability_count = 1
                        state.last_image_hash = current_hash

                    # === 하이브리드 OCR 트리거 로직 ===
                    should_ocr = False
                    ocr_reason = ""

                    # 조건 1: 화면 안정화 + 새 화면
                    if (
                        state.stability_count >= stability_threshold
                        and current_hash != state.last_stable_hash
                    ):
                        should_ocr = True
                        ocr_reason = "안정화"
                        state.last_stable_hash = current_hash

                    # 조건 2: 1초 경과 (이펙트 있어도 OCR 시도)
                    elif current_time - last_ocr_time >= FORCE_OCR_INTERVAL:
                        should_ocr = True
                        ocr_reason = "시간 기반"

                    if not should_ocr:
                        await asyncio.sleep(poll_interval)
                        continue

                    print(f"[SSE] OCR 시작 ({ocr_reason})...", flush=True)
                    last_ocr_time = current_time

                    # OCR 실행 (GPU 세마포어 + 타임아웃 적용)
                    # GPU 세마포어: TTS와 동시 실행 방지 (메모리 부족 크래시 방지)
                    ocr_start = time.time()
                    try:
                        async with gpu_semaphore_context():
                            print(f"[SSE] GPU 세마포어 통과", flush=True)
                            results = await asyncio.wait_for(
                                ocr.recognize(image),
                                timeout=10.0,  # 10초 타임아웃
                            )
                        print(
                            f"[SSE] OCR 완료: {len(results) if results else 0}개 결과, {time.time() - ocr_start:.2f}초",
                            flush=True,
                        )
                    except asyncio.TimeoutError:
                        print("[SSE] OCR 타임아웃 (10초)", flush=True)
                        await asyncio.sleep(poll_interval)
                        continue

                    if results:
                        sorted_results = sorted(
                            [r for r in results if r.confidence >= min_confidence],
                            key=lambda r: r.bounding_box.y if r.bounding_box else 0,
                        )

                        if sorted_results:
                            combined_text = "\n".join(r.text for r in sorted_results)
                            avg_confidence = sum(
                                r.confidence for r in sorted_results
                            ) / len(sorted_results)

                            # 새로운 대사인지 확인
                            is_new = combined_text != state.last_text
                            if is_new:
                                state.last_text = combined_text
                                print(
                                    f"[SSE] 새 대사 감지: '{combined_text[:50]}...' (신뢰도: {avg_confidence:.2f})",
                                    flush=True,
                                )
                                yield {
                                    "event": "dialogue",
                                    "data": json.dumps(
                                        {
                                            "type": "dialogue",
                                            "text": combined_text,
                                            "confidence": avg_confidence,
                                            "timestamp": time.time(),
                                            "is_new": True,
                                        }
                                    ),
                                }

                except asyncio.CancelledError:
                    print(f"[SSE] 스트림 취소됨", flush=True)
                    break
                except Exception as e:
                    print(f"[SSE] 루프 에러: {e}", flush=True)
                    traceback.print_exc()
                    yield {
                        "event": "error",
                        "data": json.dumps({"type": "error", "message": str(e)}),
                    }

                await asyncio.sleep(poll_interval)

        except Exception as e:
            print(f"[SSE] 스트림 설정 에러: {e}", flush=True)
            traceback.print_exc()
            yield {
                "event": "error",
                "data": json.dumps({"type": "setup_error", "message": str(e)}),
            }
        finally:
            # 정리
            if hwnd in _window_stability:
                del _window_stability[hwnd]
            try:
                capture.close()
            except:
                pass

    return EventSourceResponse(event_generator())
