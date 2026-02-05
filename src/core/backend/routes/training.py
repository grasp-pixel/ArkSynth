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
            extracted_path=config.extracted_path,  # 언어별 폴더는 _get_audio_files에서 처리
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


class StartTrainingRequest(BaseModel):
    """단일 학습 요청"""

    mode: str = "prepare"  # "prepare" (Zero-shot) 또는 "finetune" (실제 학습)


class BatchTrainingRequest(BaseModel):
    """일괄 학습 요청"""

    char_ids: Optional[list[str]] = None  # None이면 음성 있는 모든 캐릭터
    mode: str = "prepare"  # "prepare" (Zero-shot) 또는 "finetune" (실제 학습)


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
async def start_training(char_id: str, request: StartTrainingRequest = StartTrainingRequest()):
    """단일 캐릭터 학습 시작

    Args:
        char_id: 캐릭터 ID
        request.mode: "prepare" (Zero-shot 준비) 또는 "finetune" (실제 학습)
    """
    manager = get_training_manager()
    model_manager = get_model_manager()
    mapper = get_character_mapper()

    # 캐릭터 확인
    if not mapper.has_voice(char_id, "voice"):
        raise HTTPException(
            status_code=404,
            detail=f"캐릭터 음성 파일이 없습니다: {char_id}",
        )

    # 이미 학습된 경우 (finetune 모드는 기존 준비된 것도 다시 학습 가능)
    if request.mode == "prepare" and model_manager.is_trained(char_id):
        raise HTTPException(
            status_code=400,
            detail=f"이미 준비된 캐릭터입니다: {char_id}",
        )

    # finetune 모드: 전처리 완료 확인 필수
    if request.mode == "finetune":
        gpt_config = GPTSoVITSConfig(
            models_path=config.models_path / "gpt_sovits",
            extracted_path=config.extracted_path,
        )
        preprocessed_dir = gpt_config.get_preprocessed_audio_path(char_id)
        has_preprocessed = preprocessed_dir.exists() and any(preprocessed_dir.glob("*.wav"))
        if not has_preprocessed:
            raise HTTPException(
                status_code=400,
                detail=f"먼저 '음성 준비'를 실행해주세요. 전처리된 오디오가 없습니다: {char_id}",
            )

    # 캐릭터 이름
    char_name = mapper.get_character_name(char_id, game_lang=config.game_language)

    # 학습 매니저 시작 (동기적으로 먼저 시작)
    await ensure_manager_running()
    mode_label = "학습" if request.mode == "finetune" else "준비"
    logger.info(f"{mode_label} 시작: {char_id} ({char_name}) [mode={request.mode}]")

    # 학습 큐에 추가 (mode 전달)
    job = await manager.queue_training(char_id, char_name, mode=request.mode)

    return {"job": job.to_dict()}


@router.post("/start-batch")
async def start_batch_training(request: BatchTrainingRequest):
    """일괄 학습 시작

    Args:
        request.char_ids: 캐릭터 ID 목록 (None이면 모든 음성 캐릭터)
        request.mode: "prepare" (Zero-shot 준비) 또는 "finetune" (실제 학습)
    """
    logger.info(f"[start-batch] 요청 수신: char_ids={request.char_ids}, mode={request.mode}")
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

    # finetune 모드용 전처리 확인을 위한 config
    gpt_config = None
    if request.mode == "finetune":
        gpt_config = GPTSoVITSConfig(
            models_path=config.models_path / "gpt_sovits",
            extracted_path=config.extracted_path,
        )

    # 캐릭터 정보 수집
    characters = []
    for char_id in char_ids:
        # prepare 모드: 미준비 캐릭터만
        # finetune 모드: 미학습(finetuned가 아닌) + 전처리된 캐릭터만
        if request.mode == "prepare":
            if model_manager.is_trained(char_id):
                continue
        else:  # finetune
            if model_manager.has_trained_model(char_id):
                continue
            # 전처리 완료 확인 (preprocessed 폴더에 WAV 파일 있는지)
            preprocessed_dir = gpt_config.get_preprocessed_audio_path(char_id)
            has_preprocessed = preprocessed_dir.exists() and any(preprocessed_dir.glob("*.wav"))
            if not has_preprocessed:
                logger.warning(f"전처리 미완료, 스킵: {char_id}")
                continue

        char_name = mapper.get_character_name(char_id, game_lang=config.game_language)
        characters.append((char_id, char_name))

    if not characters:
        mode_label = "학습" if request.mode == "finetune" else "준비"
        return {
            "jobs": [],
            "total": 0,
            "message": f"{mode_label}할 캐릭터가 없습니다 (이미 모두 완료됨)",
        }

    # 학습 매니저 시작 (동기적으로 먼저 시작)
    await ensure_manager_running()
    mode_label = "학습" if request.mode == "finetune" else "준비"
    logger.info(f"일괄 {mode_label} 시작: {len(characters)}개 캐릭터 [mode={request.mode}]")

    # 일괄 큐 추가 (mode 전달)
    jobs = await manager.queue_batch_training(characters, mode=request.mode)

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
    """학습 완료된 모델 목록

    각 모델의 can_finetune 필드는 해당 캐릭터가 finetune 가능한지를 나타냅니다.
    (prepared 상태이고 전처리가 완료된 경우에만 finetune 가능)
    """
    model_manager = get_model_manager()
    models = model_manager.list_all_models()

    # 전처리 상태 확인을 위한 config
    gpt_config = GPTSoVITSConfig(
        models_path=config.models_path / "gpt_sovits",
        extracted_path=config.extracted_path,
    )

    result_models = []
    for m in models:
        model_type = model_manager.get_model_type(m.char_id)
        # 전처리 상태 확인 (preprocessed 폴더에 WAV + TXT 파일 있는지)
        preprocessed_dir = gpt_config.get_preprocessed_audio_path(m.char_id)
        segment_count = 0
        is_preprocessed = False
        if preprocessed_dir.exists():
            wav_files = list(preprocessed_dir.glob("*.wav"))
            txt_files = list(preprocessed_dir.glob("*.txt"))
            segment_count = len(wav_files)
            is_preprocessed = segment_count > 0 and len(txt_files) > 0
        can_finetune = model_type == "prepared" and is_preprocessed

        result_models.append({
            "char_id": m.char_id,
            "char_name": m.char_name,
            "trained_at": m.trained_at,
            "language": m.language,
            "model_type": model_type,
            "epochs_sovits": m.epochs_sovits,
            "epochs_gpt": m.epochs_gpt,
            "is_preprocessed": is_preprocessed,
            "segment_count": segment_count,
            "can_finetune": can_finetune,
        })

    return {
        "models": result_models,
        "total": len(result_models),
    }


@router.get("/models/{char_id}/type")
async def get_model_type(char_id: str):
    """모델 타입 조회

    Returns:
        model_type: "none" (미준비), "prepared" (Zero-shot), "finetuned" (학습됨)
        is_preprocessed: bool - 전처리 완료 여부 (finetune 가능 여부 판단용)
        can_finetune: bool - finetune 가능 여부 (prepared이고 전처리 완료됨)
    """
    model_manager = get_model_manager()
    model_type = model_manager.get_model_type(char_id)

    # 전처리 상태 확인 (preprocessed 폴더에 WAV + TXT 파일 있는지)
    gpt_config = GPTSoVITSConfig(
        models_path=config.models_path / "gpt_sovits",
        extracted_path=config.extracted_path,
    )
    preprocessed_dir = gpt_config.get_preprocessed_audio_path(char_id)
    segment_count = 0
    is_preprocessed = False
    if preprocessed_dir.exists():
        wav_files = list(preprocessed_dir.glob("*.wav"))
        txt_files = list(preprocessed_dir.glob("*.txt"))
        segment_count = len(wav_files)
        is_preprocessed = segment_count > 0 and len(txt_files) > 0

    # finetune 가능 여부: prepared 상태이고 전처리 완료됨
    can_finetune = model_type == "prepared" and is_preprocessed

    return {
        "char_id": char_id,
        "model_type": model_type,
        "is_preprocessed": is_preprocessed,
        "segment_count": segment_count,
        "can_finetune": can_finetune,
    }


@router.get("/models/{char_id}/preprocessed")
async def check_preprocessing_status(char_id: str):
    """전처리 상태 확인

    음성 준비(prepare) 단계에서 Whisper로 분할된 세그먼트가 있는지 확인합니다.
    finetune(학습) 모드를 실행하기 전에 이 상태를 확인해야 합니다.

    Returns:
        is_preprocessed: bool - 전처리 완료 여부
        segment_count: int - 전처리된 세그먼트 수 (0이면 미완료)
        preprocessed_path: str - 전처리된 파일 경로
    """
    gpt_config = GPTSoVITSConfig(
        models_path=config.models_path / "gpt_sovits",
        extracted_path=config.extracted_path,
    )

    preprocessed_dir = gpt_config.get_preprocessed_audio_path(char_id)

    is_preprocessed = False
    segment_count = 0

    # 새 구조: preprocessed 폴더에서 WAV + TXT 파일 쌍 확인
    if preprocessed_dir.exists():
        wav_files = list(preprocessed_dir.glob("*.wav"))
        txt_files = list(preprocessed_dir.glob("*.txt"))
        segment_count = len(wav_files)
        # WAV와 TXT 파일이 모두 있어야 전처리 완료
        is_preprocessed = segment_count > 0 and len(txt_files) > 0

    return {
        "char_id": char_id,
        "is_preprocessed": is_preprocessed,
        "segment_count": segment_count,
        "preprocessed_path": str(preprocessed_dir) if is_preprocessed else None,
    }


@router.get("/models/{char_id}/engine-status")
async def get_engine_specific_model_status(char_id: str):
    """GPT-SoVITS 모델 상태 조회

    Returns:
        char_id: 캐릭터 ID
        gpt_sovits: GPT-SoVITS 상태
            - model_type: "none" | "prepared" | "finetuned"
            - is_preprocessed: 전처리 완료 여부
            - segment_count: 전처리된 세그먼트 수
            - can_finetune: finetune 가능 여부
    """
    # GPT-SoVITS 상태
    model_manager = get_model_manager()
    gpt_model_type = model_manager.get_model_type(char_id)

    gpt_config = GPTSoVITSConfig(
        models_path=config.models_path / "gpt_sovits",
        extracted_path=config.extracted_path,
    )
    preprocessed_dir = gpt_config.get_preprocessed_audio_path(char_id)
    segment_count = 0
    is_preprocessed = False
    if preprocessed_dir.exists():
        wav_files = list(preprocessed_dir.glob("*.wav"))
        txt_files = list(preprocessed_dir.glob("*.txt"))
        segment_count = len(wav_files)
        is_preprocessed = segment_count > 0 and len(txt_files) > 0

    gpt_can_finetune = gpt_model_type == "prepared" and is_preprocessed

    return {
        "char_id": char_id,
        "gpt_sovits": {
            "model_type": gpt_model_type,
            "is_preprocessed": is_preprocessed,
            "segment_count": segment_count,
            "can_finetune": gpt_can_finetune,
        },
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
