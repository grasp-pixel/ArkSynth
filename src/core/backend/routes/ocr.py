"""OCR API 라우트"""

import base64
import io
from typing import Annotated

from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from pydantic import BaseModel
from PIL import Image

router = APIRouter()


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
    except ImportError:
        raise HTTPException(status_code=501, detail="OCR module not available. Install with: uv pip install paddlepaddle paddleocr")
    except Exception as e:
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
