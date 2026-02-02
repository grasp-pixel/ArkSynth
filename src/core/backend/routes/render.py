"""에피소드 렌더링 API 라우터"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from ..config import config
from ...cache import RenderCache, RenderManager, RenderProgress, RenderStatus
from ...story.loader import StoryLoader

logger = logging.getLogger(__name__)
router = APIRouter()

# 전역 매니저 인스턴스
_render_cache: RenderCache | None = None
_render_manager: RenderManager | None = None
_story_loader: StoryLoader | None = None


def get_render_cache() -> RenderCache:
    global _render_cache
    if _render_cache is None:
        _render_cache = RenderCache(config.rendered_path)
    return _render_cache


def get_render_manager() -> RenderManager:
    global _render_manager
    if _render_manager is None:
        _render_manager = RenderManager(get_render_cache())
    return _render_manager


def get_story_loader() -> StoryLoader:
    global _story_loader
    if _story_loader is None:
        _story_loader = StoryLoader(config.gamedata_path)
    return _story_loader


# === Request/Response 모델 ===


class StartRenderRequest(BaseModel):
    """렌더링 시작 요청"""

    language: str = "ko"


class RenderProgressResponse(BaseModel):
    """렌더링 진행 응답"""

    episode_id: str
    status: str
    total: int
    completed: int
    progress_percent: float
    current_index: Optional[int] = None
    current_text: Optional[str] = None
    error: Optional[str] = None


# === 엔드포인트 ===


@router.get("/status")
async def get_render_status():
    """전체 렌더링 상태"""
    manager = get_render_manager()
    cache = get_render_cache()

    cached_episodes = cache.list_cached_episodes()
    current_progress = manager.get_progress()

    return {
        "is_rendering": manager.is_rendering,
        "current_episode_id": manager.current_episode_id,
        "cached_episodes": cached_episodes,
        "cached_count": len(cached_episodes),
        "current_progress": (
            {
                "episode_id": current_progress.episode_id,
                "status": current_progress.status.value,
                "total": current_progress.total,
                "completed": current_progress.completed,
                "progress_percent": current_progress.progress_percent,
            }
            if current_progress
            else None
        ),
    }


@router.post("/start/{episode_id:path}")
async def start_render(
    episode_id: str,
    request: StartRenderRequest,
    background_tasks: BackgroundTasks,
):
    """에피소드 렌더링 시작

    Args:
        episode_id: 에피소드 ID (예: main/0-1)
    """
    manager = get_render_manager()
    cache = get_render_cache()
    loader = get_story_loader()

    # 이미 렌더링 중인지 확인
    if manager.is_rendering and manager.current_episode_id != episode_id:
        raise HTTPException(
            status_code=400,
            detail=f"이미 다른 에피소드 렌더링 중: {manager.current_episode_id}",
        )

    # 이미 완료된 경우
    if cache.is_complete(episode_id):
        completed, total = cache.get_progress(episode_id)
        return {
            "episode_id": episode_id,
            "status": "completed",
            "total": total,
            "completed": completed,
            "progress_percent": 100.0,
            "message": "이미 렌더링 완료됨",
        }

    # 에피소드 대사 로드
    try:
        episode = loader.load_episode(episode_id)
        if not episode:
            raise HTTPException(
                status_code=404,
                detail=f"에피소드를 찾을 수 없습니다: {episode_id}",
            )
    except Exception as e:
        logger.error(f"에피소드 로드 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"에피소드 로드 실패: {str(e)}",
        )

    # 대사 목록 생성 (음성 합성 대상만)
    dialogues = []
    for i, dialogue in enumerate(episode.dialogues):
        if dialogue.type == "dialogue" and dialogue.text:
            dialogues.append(
                {
                    "index": i,
                    "char_id": dialogue.character_id,
                    "text": dialogue.text,
                }
            )

    if not dialogues:
        raise HTTPException(
            status_code=400,
            detail="렌더링할 대사가 없습니다",
        )

    # 렌더링 시작
    progress = await manager.start_render(episode_id, dialogues, request.language)

    return {
        "episode_id": episode_id,
        "status": progress.status.value,
        "total": progress.total,
        "completed": progress.completed,
        "progress_percent": progress.progress_percent,
        "message": "렌더링 시작됨",
    }


@router.post("/cancel/{episode_id:path}")
async def cancel_render(episode_id: str):
    """렌더링 취소"""
    manager = get_render_manager()

    if not manager.is_rendering:
        raise HTTPException(
            status_code=400,
            detail="렌더링 중인 작업이 없습니다",
        )

    if manager.current_episode_id != episode_id:
        raise HTTPException(
            status_code=400,
            detail=f"해당 에피소드가 렌더링 중이 아닙니다: {episode_id}",
        )

    success = await manager.cancel_render(episode_id)

    return {"cancelled": success}


@router.get("/progress/{episode_id:path}")
async def get_render_progress(episode_id: str):
    """렌더링 진행률 조회"""
    manager = get_render_manager()
    cache = get_render_cache()

    # 현재 렌더링 중인 경우
    progress = manager.get_progress(episode_id)
    if progress:
        return {
            "episode_id": episode_id,
            "status": progress.status.value,
            "total": progress.total,
            "completed": progress.completed,
            "progress_percent": progress.progress_percent,
            "current_index": progress.current_index,
            "current_text": progress.current_text,
            "error": progress.error,
        }

    # 캐시 확인
    if cache.has_cache(episode_id):
        completed, total = cache.get_progress(episode_id)
        status = "completed" if completed >= total else "partial"
        return {
            "episode_id": episode_id,
            "status": status,
            "total": total,
            "completed": completed,
            "progress_percent": (completed / total * 100) if total > 0 else 0,
            "current_index": None,
            "current_text": None,
            "error": None,
        }

    # 캐시 없음
    return {
        "episode_id": episode_id,
        "status": "not_started",
        "total": 0,
        "completed": 0,
        "progress_percent": 0,
        "current_index": None,
        "current_text": None,
        "error": None,
    }


@router.get("/audio/{episode_id:path}/{index}")
async def get_rendered_audio(episode_id: str, index: int):
    """렌더링된 오디오 파일 반환"""
    cache = get_render_cache()

    audio_path = cache.get_audio(episode_id, index)
    if not audio_path:
        raise HTTPException(
            status_code=404,
            detail=f"오디오 파일 없음: {episode_id}[{index}]",
        )

    return FileResponse(
        audio_path,
        media_type="audio/wav",
        filename=f"{episode_id.replace('/', '_')}_{index:04d}.wav",
    )


@router.get("/cache/{episode_id:path}")
async def get_cache_info(episode_id: str):
    """캐시 정보 조회"""
    cache = get_render_cache()

    if not cache.has_cache(episode_id):
        raise HTTPException(
            status_code=404,
            detail=f"캐시 없음: {episode_id}",
        )

    meta = cache.get_meta(episode_id)
    if not meta:
        raise HTTPException(
            status_code=500,
            detail="메타데이터 로드 실패",
        )

    return {
        "episode_id": meta.episode_id,
        "total_dialogues": meta.total_dialogues,
        "rendered_count": meta.rendered_count,
        "rendered_at": meta.rendered_at,
        "language": meta.language,
        "cache_size": cache.get_cache_size(episode_id),
        "audios": [
            {
                "index": a.index,
                "char_id": a.char_id,
                "text": a.text[:50] + "..." if len(a.text) > 50 else a.text,
                "duration": a.duration,
            }
            for a in meta.audios
        ],
    }


@router.delete("/cache/{episode_id:path}")
async def delete_cache(episode_id: str):
    """캐시 삭제"""
    cache = get_render_cache()

    if not cache.has_cache(episode_id):
        raise HTTPException(
            status_code=404,
            detail=f"캐시 없음: {episode_id}",
        )

    success = cache.delete_cache(episode_id)

    return {"deleted": success}


@router.get("/stream/{episode_id:path}")
async def render_progress_stream(episode_id: str):
    """렌더링 진행률 SSE 스트리밍"""
    manager = get_render_manager()

    async def event_generator():
        queue: asyncio.Queue[RenderProgress] = asyncio.Queue()

        def on_progress(progress: RenderProgress):
            if progress.episode_id == episode_id:
                try:
                    queue.put_nowait(progress)
                except asyncio.QueueFull:
                    pass

        manager.add_progress_callback(on_progress)

        try:
            # 초기 상태 전송
            initial = manager.get_progress(episode_id)
            if initial:
                data = {
                    "episode_id": initial.episode_id,
                    "status": initial.status.value,
                    "total": initial.total,
                    "completed": initial.completed,
                    "progress_percent": initial.progress_percent,
                    "current_index": initial.current_index,
                    "current_text": initial.current_text,
                }
                yield f"event: progress\ndata: {json.dumps(data)}\n\n"

            while True:
                try:
                    progress = await asyncio.wait_for(queue.get(), timeout=30.0)
                    data = {
                        "episode_id": progress.episode_id,
                        "status": progress.status.value,
                        "total": progress.total,
                        "completed": progress.completed,
                        "progress_percent": progress.progress_percent,
                        "current_index": progress.current_index,
                        "current_text": progress.current_text,
                        "error": progress.error,
                    }
                    yield f"event: progress\ndata: {json.dumps(data)}\n\n"

                    # 완료/취소/실패 시 스트림 종료
                    if progress.status in (
                        RenderStatus.COMPLETED,
                        RenderStatus.CANCELLED,
                        RenderStatus.FAILED,
                    ):
                        yield f"event: complete\ndata: {json.dumps(data)}\n\n"
                        break

                except asyncio.TimeoutError:
                    # 킵얼라이브
                    yield f"event: ping\ndata: {{}}\n\n"

        finally:
            manager.remove_progress_callback(on_progress)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
