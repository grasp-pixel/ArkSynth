"""OCR API 라우트"""

import base64
import io
import time
from typing import Annotated

from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from fastapi.responses import Response
from pydantic import BaseModel
from PIL import Image

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
            image = image.crop((
                0,
                top_margin,
                image.width,
                image.height,
            ))

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
    min_confidence: Annotated[float, Query(description="최소 신뢰도")] = 0.5,
    ignore_top_ratio: Annotated[float, Query(description="상단 무시 비율 (UI 제외)")] = 0.15,
):
    """윈도우에서 대사 감지 (캡처 + OCR)"""
    import traceback

    try:
        from ...ocr import ScreenCapture, EasyOCRProvider

        capture = ScreenCapture()
        image = await capture.capture_window_async(hwnd)
        capture.close()

        if image is None:
            raise HTTPException(status_code=400, detail="Failed to capture window")

        # 상단 UI 영역 제외 (LOG, AUTO, SKIP 등)
        if ignore_top_ratio > 0:
            top_margin = int(image.height * ignore_top_ratio)
            image = image.crop((
                0,
                top_margin,
                image.width,
                image.height,
            ))

        ocr = EasyOCRProvider(language=lang)
        results = await ocr.recognize(image)

        if results:
            # 모든 결과를 y좌표 순으로 정렬하여 합치기
            sorted_results = sorted(
                [r for r in results if r.confidence >= min_confidence],
                key=lambda r: r.bounding_box.y if r.bounding_box else 0
            )
            if sorted_results:
                combined_text = "\n".join(r.text for r in sorted_results)
                avg_confidence = sum(r.confidence for r in sorted_results) / len(sorted_results)
                return DetectDialogueResponse(
                    text=combined_text,
                    confidence=avg_confidence,
                    timestamp=time.time(),
                )

        return DetectDialogueResponse(
            text=None,
            confidence=0.0,
            timestamp=time.time(),
        )
    except ImportError as e:
        print(f"[OCR] ImportError: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=501, detail=f"OCR module not available: {e}")
    except HTTPException:
        raise
    except Exception as e:
        print(f"[OCR] Error in detect_window_dialogue: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


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
                    ) if r.bounding_box else None,
                )
                for r in results
            ],
            language=lang,
        )
    except ImportError:
        raise HTTPException(status_code=501, detail="OCR module not available. Install with: uv pip install paddlepaddle paddleocr")
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
            raise HTTPException(status_code=400, detail=f"Invalid monitor ID: {monitor}")

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
    min_confidence: Annotated[float, Query(description="최소 신뢰도")] = 0.5,
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
            raise HTTPException(status_code=400, detail=f"Invalid monitor ID: {monitor}")

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
        raise HTTPException(status_code=400, detail="Custom region not set. Call POST /region/custom first.")

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
