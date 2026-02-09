"""앱 업데이트 라우터"""

import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from ..config import config, get_app_version
from ...updater import AppUpdater, UpdateProgress, get_updater

logger = logging.getLogger(__name__)

router = APIRouter()

# 업데이트 작업 상태
_update_task: Optional[asyncio.Task] = None
_update_progress_queue: Optional[asyncio.Queue] = None


def _get_updater() -> AppUpdater:
    """설정에서 리포 정보를 읽어 업데이터 반환"""
    return get_updater(repo=config.update_repo)


@router.get("/check")
async def check_update():
    """업데이트 확인"""
    updater = _get_updater()

    try:
        info = await updater.check_update()
    except Exception as e:
        logger.exception("업데이트 확인 실패")
        raise HTTPException(status_code=502, detail=str(e))

    return {
        "available": info.available,
        "current_version": info.current_version,
        "latest_version": info.latest_version,
        "changelog": info.changelog,
        "download_size": info.size,
        "minimum_version": info.minimum_version,
    }


@router.post("/start")
async def start_update():
    """업데이트 시작"""
    global _update_task, _update_progress_queue

    # 이미 진행 중인지 확인
    if _update_task and not _update_task.done():
        raise HTTPException(status_code=409, detail="이미 업데이트가 진행 중입니다")

    updater = _get_updater()

    # 먼저 업데이트 확인
    try:
        info = await updater.check_update()
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

    if not info.available:
        raise HTTPException(status_code=404, detail="사용 가능한 업데이트가 없습니다")

    if not info.download_url:
        raise HTTPException(status_code=404, detail="다운로드 URL을 찾을 수 없습니다")

    # 진행률 큐 생성
    _update_progress_queue = asyncio.Queue()

    async def progress_callback(progress: UpdateProgress):
        if _update_progress_queue:
            await _update_progress_queue.put(progress)

    # 업데이트 작업 시작
    async def update_task():
        try:
            return await updater.apply_update(info, progress_callback)
        except Exception as e:
            logger.exception("업데이트 작업 실패")
            await progress_callback(UpdateProgress(
                stage="error", progress=0, message="업데이트 실패", error=str(e),
            ))
            return False

    _update_task = asyncio.create_task(update_task())

    return {
        "status": "started",
        "message": "업데이트가 시작되었습니다",
        "version": info.latest_version,
    }


@router.get("/stream")
async def stream_update_progress():
    """업데이트 진행률 SSE 스트림"""
    global _update_progress_queue

    if _update_progress_queue is None:
        raise HTTPException(status_code=404, detail="진행 중인 업데이트가 없습니다")

    async def event_generator():
        try:
            while True:
                try:
                    progress = await asyncio.wait_for(
                        _update_progress_queue.get(),
                        timeout=30.0,
                    )

                    data = {
                        "stage": progress.stage,
                        "progress": progress.progress,
                        "message": progress.message,
                        "error": progress.error,
                    }
                    yield f"event: progress\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

                    # 완료 또는 에러 시 종료
                    if progress.stage in ("complete", "error"):
                        if progress.stage == "complete":
                            yield f"event: complete\ndata: {json.dumps({'success': True})}\n\n"
                        else:
                            yield f"event: error\ndata: {json.dumps({'error': progress.error}, ensure_ascii=False)}\n\n"
                        break

                except asyncio.TimeoutError:
                    # keep-alive
                    yield f"event: ping\ndata: {json.dumps({'status': 'alive'})}\n\n"

        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/cancel")
async def cancel_update():
    """업데이트 취소"""
    global _update_task

    if _update_task is None or _update_task.done():
        raise HTTPException(status_code=404, detail="진행 중인 업데이트가 없습니다")

    updater = _get_updater()
    updater.cancel()

    return {"status": "cancelling", "message": "업데이트 취소 요청됨"}


@router.get("/version")
async def get_version():
    """현재 앱 버전 조회"""
    return {"version": get_app_version()}
