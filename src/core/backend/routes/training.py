"""음성 모델 학습 API 라우터"""

import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..config import config
from ...voice.gpt_sovits import (
    GPTSoVITSConfig,
    GPTSoVITSModelManager,
    TrainingManager,
    TrainingJob,
    TrainingStatus,
)
from ...voice.character_mapping import CharacterVoiceMapper

logger = logging.getLogger(__name__)
router = APIRouter()

# 전역 매니저 인스턴스
_training_manager: TrainingManager | None = None
_model_manager: GPTSoVITSModelManager | None = None
_character_mapper: CharacterVoiceMapper | None = None


def get_training_manager() -> TrainingManager:
    global _training_manager, _model_manager
    if _training_manager is None:
        gpt_config = GPTSoVITSConfig(
            models_path=config.models_path / "gpt_sovits",
            extracted_path=config.extracted_path / config.voice_language,
        )
        _model_manager = GPTSoVITSModelManager(gpt_config)
        _training_manager = TrainingManager(gpt_config, _model_manager)
    return _training_manager


def get_model_manager() -> GPTSoVITSModelManager:
    get_training_manager()  # 초기화 보장
    return _model_manager


def get_character_mapper() -> CharacterVoiceMapper:
    global _character_mapper
    if _character_mapper is None:
        _character_mapper = CharacterVoiceMapper(
            extracted_path=config.extracted_path,
            gamedata_path=config.gamedata_yostar_path,
        )
    return _character_mapper


# === Request/Response 모델 ===


class BatchTrainingRequest(BaseModel):
    """일괄 학습 요청"""

    char_ids: Optional[list[str]] = None  # None이면 음성 있는 모든 캐릭터


class TrainingJobResponse(BaseModel):
    """학습 작업 응답"""

    job_id: str
    char_id: str
    char_name: str
    status: str
    progress: float
    current_epoch: int
    total_epochs: int
    message: str
    error_message: Optional[str] = None


# === 엔드포인트 ===


@router.get("/status")
async def get_training_status():
    """전체 학습 상태 요약"""
    manager = get_training_manager()
    model_manager = get_model_manager()
    mapper = get_character_mapper()

    # 음성 있는 캐릭터 수
    available_chars = mapper.get_available_characters("voice")

    return {
        **manager.get_status_summary(),
        "total_trainable": len(available_chars),
    }


@router.get("/jobs")
async def list_training_jobs(status: Optional[str] = None):
    """학습 작업 목록"""
    manager = get_training_manager()
    jobs = manager.get_all_jobs()

    if status:
        jobs = [j for j in jobs if j.status.value == status]

    return {
        "jobs": [j.to_dict() for j in jobs],
        "total": len(jobs),
    }


@router.get("/jobs/{job_id}")
async def get_training_job(job_id: str):
    """특정 작업 상태"""
    manager = get_training_manager()
    job = manager.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return job.to_dict()


@router.post("/start/{char_id}")
async def start_training(char_id: str):
    """단일 캐릭터 학습 시작"""
    manager = get_training_manager()
    model_manager = get_model_manager()
    mapper = get_character_mapper()

    # 캐릭터 확인
    if not mapper.has_voice(char_id, "voice"):
        raise HTTPException(
            status_code=404,
            detail=f"캐릭터 음성 파일이 없습니다: {char_id}",
        )

    # 이미 학습된 경우
    if model_manager.is_trained(char_id):
        raise HTTPException(
            status_code=400,
            detail=f"이미 학습된 캐릭터입니다: {char_id}",
        )

    # 캐릭터 이름
    char_name = mapper.get_character_name(char_id, game_lang=config.game_language)

    # 학습 매니저 시작 (동기적으로 먼저 시작)
    await ensure_manager_running()
    logger.info(f"학습 시작: {char_id} ({char_name})")

    # 학습 큐에 추가
    job = await manager.queue_training(char_id, char_name)

    return {"job": job.to_dict()}


@router.post("/start-batch")
async def start_batch_training(request: BatchTrainingRequest):
    """일괄 학습 시작"""
    logger.info(f"[start-batch] 요청 수신: char_ids={request.char_ids}")
    manager = get_training_manager()
    logger.info(f"[start-batch] manager id: {id(manager)}, is_running: {manager._is_running}")
    model_manager = get_model_manager()
    mapper = get_character_mapper()

    # 대상 캐릭터 결정
    if request.char_ids:
        char_ids = request.char_ids
    else:
        # 음성 있는 모든 캐릭터
        char_ids = mapper.get_available_characters(config.voice_language)

    # 캐릭터 정보 수집 (미학습 캐릭터만)
    characters = []
    for char_id in char_ids:
        if model_manager.is_trained(char_id):
            continue
        char_name = mapper.get_character_name(char_id, game_lang=config.game_language)
        characters.append((char_id, char_name))

    if not characters:
        return {
            "jobs": [],
            "total": 0,
            "message": "학습할 캐릭터가 없습니다 (이미 모두 학습됨)",
        }

    # 학습 매니저 시작 (동기적으로 먼저 시작)
    await ensure_manager_running()
    logger.info(f"일괄 학습 시작: {len(characters)}개 캐릭터")

    # 일괄 큐 추가
    jobs = await manager.queue_batch_training(characters)

    return {
        "jobs": [j.to_dict() for j in jobs],
        "total": len(jobs),
    }


@router.post("/cancel/{job_id}")
async def cancel_training(job_id: str):
    """학습 취소"""
    manager = get_training_manager()
    success = await manager.cancel_job(job_id)

    if not success:
        raise HTTPException(
            status_code=400,
            detail="작업을 취소할 수 없습니다",
        )

    return {"cancelled": True}


@router.get("/models")
async def list_trained_models():
    """학습 완료된 모델 목록"""
    model_manager = get_model_manager()
    models = model_manager.list_all_models()

    return {
        "models": [
            {
                "char_id": m.char_id,
                "char_name": m.char_name,
                "trained_at": m.trained_at,
                "language": m.language,
            }
            for m in models
        ],
        "total": len(models),
    }


@router.delete("/models/{char_id}")
async def delete_model(char_id: str):
    """모델 삭제"""
    model_manager = get_model_manager()
    success = model_manager.delete_model(char_id)

    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"모델을 찾을 수 없습니다: {char_id}",
        )

    return {"deleted": True}


@router.delete("/models")
async def delete_all_models():
    """모든 모델 삭제"""
    model_manager = get_model_manager()
    models = model_manager.list_all_models()

    deleted_count = 0
    for model in models:
        if model_manager.delete_model(model.char_id):
            deleted_count += 1

    return {
        "deleted": True,
        "deleted_count": deleted_count,
    }


@router.get("/stream")
async def training_progress_stream():
    """학습 진행률 SSE 스트리밍"""
    manager = get_training_manager()
    logger.info(f"[SSE] 스트림 연결됨, manager id: {id(manager)}, is_running: {manager._is_running}")
    logger.info(f"[SSE] 현재 jobs 수: {len(manager._jobs)}, 큐 크기: {manager._queue.qsize()}")

    async def event_generator():
        queue: asyncio.Queue[TrainingJob] = asyncio.Queue()

        def on_progress(job: TrainingJob):
            try:
                queue.put_nowait(job)
                logger.debug(f"SSE 큐에 추가: {job.char_name} {job.progress:.1%}")
            except asyncio.QueueFull:
                logger.warning("SSE 큐가 가득 참")

        manager.add_progress_callback(on_progress)
        logger.info("SSE 콜백 등록됨")

        try:
            # 초기 상태 전송
            status = manager.get_status_summary()
            logger.info(f"SSE 초기 상태 전송: is_training={status.get('is_training')}")
            yield f"event: status\ndata: {json.dumps(status)}\n\n"

            while True:
                try:
                    job = await asyncio.wait_for(queue.get(), timeout=30.0)
                    logger.info(f"SSE 진행 이벤트: {job.char_name} {job.status.value} {job.progress:.1%}")
                    yield f"event: progress\ndata: {json.dumps(job.to_dict())}\n\n"

                    if job.status in (
                        TrainingStatus.COMPLETED,
                        TrainingStatus.FAILED,
                        TrainingStatus.CANCELLED,
                    ):
                        logger.info(f"SSE 완료 이벤트: {job.char_name} {job.status.value}")
                        yield f"event: complete\ndata: {json.dumps(job.to_dict())}\n\n"

                except asyncio.TimeoutError:
                    # 킵얼라이브
                    yield f"event: ping\ndata: {{}}\n\n"

        finally:
            manager.remove_progress_callback(on_progress)
            logger.info("SSE 스트림 종료")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


async def ensure_manager_running():
    """학습 매니저가 실행 중인지 확인하고 시작"""
    manager = get_training_manager()
    if not manager._is_running:
        await manager.start()
