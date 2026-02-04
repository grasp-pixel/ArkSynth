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
from ...cache import RenderCache, RenderManager, RenderProgress, RenderStatus, GroupRenderProgress
from .episodes import get_loader as get_story_loader  # episodes API와 같은 loader 사용

logger = logging.getLogger(__name__)
router = APIRouter()

# 전역 매니저 인스턴스
_render_cache: RenderCache | None = None
_render_manager: RenderManager | None = None


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


# === Request/Response 모델 ===


class StartRenderRequest(BaseModel):
    """렌더링 시작 요청"""

    language: str = "ko"
    default_char_id: Optional[str] = None  # 모델 없는 캐릭터용 기본 음성
    narrator_char_id: Optional[str] = None  # 나레이션용 캐릭터
    speaker_voice_map: Optional[dict[str, str]] = None  # 화자별 음성 매핑 {char_id: voice_char_id}
    force: bool = False  # 기존 캐시 무시하고 다시 렌더링


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


class StartGroupRenderRequest(BaseModel):
    """그룹 렌더링 시작 요청"""

    language: str = "ko"
    default_char_id: Optional[str] = None
    narrator_char_id: Optional[str] = None
    speaker_voice_map: Optional[dict[str, str]] = None
    force: bool = False


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
    logger.info(f"[Render] 렌더링 요청 - episode_id: {episode_id}")
    try:
        episode = loader.load_episode(episode_id)
        if not episode:
            raise HTTPException(
                status_code=404,
                detail=f"에피소드를 찾을 수 없습니다: {episode_id}",
            )
        logger.info(f"[Render] 에피소드 로드 완료 - title: {episode.title}, dialogues: {len(episode.dialogues)}")
        if episode.dialogues:
            first = episode.dialogues[0]
            logger.info(f"[Render] 첫 번째 대사: [{first.speaker_name}] {first.text[:50]}...")
    except Exception as e:
        logger.error(f"에피소드 로드 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"에피소드 로드 실패: {str(e)}",
        )

    # 대사 목록 생성 (음성 합성 대상만)
    dialogues = []
    for i, dialogue in enumerate(episode.dialogues):
        if dialogue.text:
            dialogues.append(
                {
                    "index": i,
                    "char_id": dialogue.speaker_id,
                    "speaker_name": dialogue.speaker_name,  # name: 접두사 매핑용
                    "text": dialogue.text,
                }
            )

    if not dialogues:
        raise HTTPException(
            status_code=400,
            detail="렌더링할 대사가 없습니다",
        )

    # 렌더링 시작
    progress = await manager.start_render(
        episode_id,
        dialogues,
        request.language,
        default_char_id=request.default_char_id,
        narrator_char_id=request.narrator_char_id,
        speaker_voice_map=request.speaker_voice_map,
        force=request.force,
    )

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


# === 그룹 렌더링 엔드포인트 ===


@router.get("/group-status")
async def get_group_render_status():
    """그룹 렌더링 상태 조회"""
    manager = get_render_manager()

    group_progress = manager.get_group_progress()

    return {
        "is_group_rendering": manager.is_group_rendering,
        "current_group_id": manager.current_group_id,
        "group_progress": (
            {
                "group_id": group_progress.group_id,
                "status": group_progress.status.value,
                "total_episodes": group_progress.total_episodes,
                "completed_episodes": group_progress.completed_episodes,
                "current_episode_id": group_progress.current_episode_id,
                "current_episode_progress": group_progress.current_episode_progress,
                "overall_progress": group_progress.overall_progress,
                "error": group_progress.error,
            }
            if group_progress
            else None
        ),
    }


@router.post("/start-group/{group_id}")
async def start_group_render(
    group_id: str,
    request: StartGroupRenderRequest,
):
    """그룹 전체 렌더링 시작

    Args:
        group_id: 그룹 ID (예: main, memory, etc.)
    """
    manager = get_render_manager()
    loader = get_story_loader()

    # 이미 렌더링 중인지 확인
    if manager.is_group_rendering:
        raise HTTPException(
            status_code=400,
            detail=f"이미 그룹 렌더링 중: {manager.current_group_id}",
        )

    if manager.is_rendering:
        raise HTTPException(
            status_code=400,
            detail=f"에피소드 렌더링 중: {manager.current_episode_id}",
        )

    # 그룹의 에피소드 목록 조회
    try:
        episodes = loader.list_group_episodes(group_id)
        if not episodes:
            raise HTTPException(
                status_code=404,
                detail=f"그룹에 에피소드가 없습니다: {group_id}",
            )
        episode_ids = [ep.id for ep in episodes]
        logger.info(f"[GroupRender] 그룹 {group_id}: {len(episode_ids)}개 에피소드")
    except Exception as e:
        logger.error(f"그룹 에피소드 조회 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"그룹 에피소드 조회 실패: {str(e)}",
        )

    # 대사 목록 가져오는 함수
    def get_dialogues(episode_id: str) -> list[dict]:
        try:
            episode = loader.load_episode(episode_id)
            if not episode:
                return []
            dialogues = []
            for i, dialogue in enumerate(episode.dialogues):
                if dialogue.text:
                    dialogues.append({
                        "index": i,
                        "char_id": dialogue.speaker_id,
                        "speaker_name": dialogue.speaker_name,
                        "text": dialogue.text,
                    })
            return dialogues
        except Exception as e:
            logger.error(f"에피소드 대사 로드 실패 ({episode_id}): {e}")
            return []

    # 그룹 렌더링 시작
    progress = await manager.start_group_render(
        group_id=group_id,
        episode_ids=episode_ids,
        get_dialogues=get_dialogues,
        language=request.language,
        default_char_id=request.default_char_id,
        narrator_char_id=request.narrator_char_id,
        speaker_voice_map=request.speaker_voice_map,
        force=request.force,
    )

    return {
        "group_id": group_id,
        "status": progress.status.value,
        "total_episodes": progress.total_episodes,
        "completed_episodes": progress.completed_episodes,
        "overall_progress": progress.overall_progress,
        "message": "그룹 렌더링 시작됨",
    }


@router.delete("/cancel-group")
async def cancel_group_render():
    """그룹 렌더링 취소"""
    manager = get_render_manager()

    if not manager.is_group_rendering:
        raise HTTPException(
            status_code=400,
            detail="그룹 렌더링 중인 작업이 없습니다",
        )

    success = await manager.cancel_group_render()

    return {"cancelled": success, "group_id": manager.current_group_id}


@router.get("/stream-group/{group_id}")
async def group_render_progress_stream(group_id: str):
    """그룹 렌더링 진행률 SSE 스트리밍"""
    manager = get_render_manager()

    async def event_generator():
        queue: asyncio.Queue[GroupRenderProgress] = asyncio.Queue()

        def on_progress(progress: GroupRenderProgress):
            if progress.group_id == group_id:
                try:
                    queue.put_nowait(progress)
                except asyncio.QueueFull:
                    pass

        manager.add_group_progress_callback(on_progress)

        try:
            # 초기 상태 전송
            initial = manager.get_group_progress()
            if initial and initial.group_id == group_id:
                data = {
                    "group_id": initial.group_id,
                    "status": initial.status.value,
                    "total_episodes": initial.total_episodes,
                    "completed_episodes": initial.completed_episodes,
                    "current_episode_id": initial.current_episode_id,
                    "current_episode_progress": initial.current_episode_progress,
                    "overall_progress": initial.overall_progress,
                }
                yield f"event: progress\ndata: {json.dumps(data)}\n\n"

            while True:
                try:
                    progress = await asyncio.wait_for(queue.get(), timeout=30.0)
                    data = {
                        "group_id": progress.group_id,
                        "status": progress.status.value,
                        "total_episodes": progress.total_episodes,
                        "completed_episodes": progress.completed_episodes,
                        "current_episode_id": progress.current_episode_id,
                        "current_episode_progress": progress.current_episode_progress,
                        "overall_progress": progress.overall_progress,
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
            manager.remove_group_progress_callback(on_progress)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
