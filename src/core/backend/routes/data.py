"""게임 데이터 관련 라우터"""

import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..config import config
from ...data import GamedataUpdater

logger = logging.getLogger(__name__)

router = APIRouter()

# 업데이트 작업 상태
_update_task: Optional[asyncio.Task] = None
_update_progress_queue: Optional[asyncio.Queue] = None
_updater: Optional[GamedataUpdater] = None


def get_updater() -> GamedataUpdater:
    """GamedataUpdater 인스턴스 가져오기"""
    global _updater
    if _updater is None:
        _updater = GamedataUpdater(config.data_path)
    return _updater


class GamedataStatusResponse(BaseModel):
    """게임 데이터 상태 응답"""

    exists: bool
    path: str
    server: str
    last_updated: Optional[str] = None
    story_count: int = 0


class UpdateRequest(BaseModel):
    """업데이트 요청"""

    server: str = "kr"


class UpdateProgress(BaseModel):
    """업데이트 진행 상태"""

    stage: str
    progress: float
    message: str
    error: Optional[str] = None


@router.get("/status", response_model=GamedataStatusResponse)
async def get_gamedata_status(server: str = "kr"):
    """게임 데이터 상태 확인"""
    logger.info(f"[data.py] get_gamedata_status called with server: {server}")
    updater = get_updater()
    status = updater.get_status(server)
    logger.info(f"[data.py] Status: exists={status.exists}, story_count={status.story_count}, path={status.path}")

    return GamedataStatusResponse(
        exists=status.exists,
        path=status.path,
        server=status.server,
        last_updated=status.last_updated,
        story_count=status.story_count,
    )


@router.post("/update/start")
async def start_update(request: UpdateRequest):
    """게임 데이터 업데이트 시작"""
    global _update_task, _update_progress_queue

    logger.info(f"[data.py] start_update called with server: {request.server}")

    # 이미 업데이트 중인지 확인
    if _update_task and not _update_task.done():
        logger.warning("[data.py] Update already in progress")
        raise HTTPException(status_code=409, detail="이미 업데이트가 진행 중입니다")

    updater = get_updater()
    logger.info(f"[data.py] Got updater, gamedata_path: {updater.gamedata_path}")

    # 진행률 큐 생성
    _update_progress_queue = asyncio.Queue()
    logger.info("[data.py] Created progress queue")

    async def progress_callback(progress):
        logger.info(f"[data.py] progress_callback called: stage={progress.stage}, progress={progress.progress}, message={progress.message}, error={progress.error}")
        if _update_progress_queue:
            try:
                await _update_progress_queue.put(progress)
                logger.debug("[data.py] Progress put to queue successfully")
            except Exception as e:
                logger.exception(f"[data.py] Error putting progress to queue: {e}")
        else:
            logger.warning("[data.py] Progress queue is None!")

    # 업데이트 작업 시작
    async def update_task():
        logger.info(f"[data.py] update_task started for server: {request.server}")
        try:
            result = await updater.update(
                server=request.server,
                on_progress=progress_callback,
            )
            logger.info(f"[data.py] update_task completed with result: {result}")
            return result
        except Exception as e:
            logger.exception(f"[data.py] update_task failed with exception: {e}")
            from ...data.gamedata_updater import UpdateProgress
            await progress_callback(
                UpdateProgress(
                    stage="error",
                    progress=0,
                    message="업데이트 실패",
                    error=str(e),
                )
            )
            return False

    _update_task = asyncio.create_task(update_task())
    logger.info("[data.py] update_task created")

    return {"status": "started", "message": "업데이트가 시작되었습니다", "server": request.server}


@router.get("/update/stream")
async def stream_update_progress():
    """업데이트 진행률 SSE 스트림"""
    global _update_progress_queue

    logger.info("[data.py] stream_update_progress called")

    if _update_progress_queue is None:
        logger.warning("[data.py] No progress queue, returning 404")
        raise HTTPException(status_code=404, detail="진행 중인 업데이트가 없습니다")

    async def event_generator():
        logger.info("[data.py] event_generator started")
        try:
            while True:
                try:
                    # 큐에서 진행률 가져오기 (타임아웃 30초)
                    logger.debug("[data.py] Waiting for progress from queue...")
                    progress = await asyncio.wait_for(
                        _update_progress_queue.get(),
                        timeout=30.0,
                    )
                    logger.info(f"[data.py] Got progress from queue: stage={progress.stage}, message={progress.message}")

                    # 진행률 전송
                    data = {
                        "stage": progress.stage,
                        "progress": progress.progress,
                        "message": progress.message,
                        "error": progress.error,
                    }
                    event_data = f"event: progress\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
                    logger.debug(f"[data.py] Yielding event: {event_data[:100]}...")
                    yield event_data

                    # 완료 또는 에러 시 종료
                    if progress.stage in ("complete", "error"):
                        logger.info(f"[data.py] Final stage reached: {progress.stage}")
                        if progress.stage == "complete":
                            yield f"event: complete\ndata: {json.dumps({'success': True})}\n\n"
                        else:
                            yield f"event: error\ndata: {json.dumps({'error': progress.error})}\n\n"
                        break

                except asyncio.TimeoutError:
                    # keep-alive
                    logger.debug("[data.py] Timeout, sending ping")
                    yield f"event: ping\ndata: {json.dumps({'status': 'alive'})}\n\n"

        except asyncio.CancelledError:
            logger.info("[data.py] event_generator cancelled")
        except Exception as e:
            logger.exception(f"[data.py] event_generator error: {e}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/update/cancel")
async def cancel_update():
    """업데이트 취소"""
    global _update_task

    if _update_task is None or _update_task.done():
        raise HTTPException(status_code=404, detail="진행 중인 업데이트가 없습니다")

    updater = get_updater()
    updater.cancel()

    return {"status": "cancelling", "message": "업데이트 취소 요청됨"}
