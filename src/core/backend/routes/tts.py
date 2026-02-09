"""TTS 관련 라우터

GPT-SoVITS 캐릭터별 음성 클로닝 지원
"""

import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional

from ..config import config
from .. import gpu_semaphore_context
from ...voice.gpt_sovits import GPTSoVITSConfig, GPTSoVITSModelManager
from ...voice.gpt_sovits.synthesizer import GPTSoVITSSynthesizer
from ...voice.gpt_sovits.training_worker import prepare_reference_audio

logger = logging.getLogger(__name__)
router = APIRouter()

# 전역 프로바이더
_gpt_synthesizer: GPTSoVITSSynthesizer | None = None
_gpt_model_manager: GPTSoVITSModelManager | None = None


def get_gpt_synthesizer() -> GPTSoVITSSynthesizer:
    global _gpt_synthesizer, _gpt_model_manager
    if _gpt_synthesizer is None:
        gpt_config = GPTSoVITSConfig(
            models_path=config.models_path / "gpt_sovits",
            extracted_path=config.extracted_path,
        )
        _gpt_model_manager = GPTSoVITSModelManager(gpt_config)
        _gpt_synthesizer = GPTSoVITSSynthesizer(gpt_config, _gpt_model_manager)
    return _gpt_synthesizer


def get_gpt_model_manager() -> GPTSoVITSModelManager:
    # ensure synthesizer is initialized
    get_gpt_synthesizer()
    return _gpt_model_manager


class SynthesizeRequest(BaseModel):
    """TTS 합성 요청

    TTS 파라미터는 GPTSoVITSConfig의 기본값을 사용합니다.
    """

    text: str
    char_id: str | None = None  # 캐릭터 ID
    engine: str | None = None  # TTS 엔진 (현재 "gpt_sovits"만 지원), None이면 글로벌 설정 사용
    language: str | None = None  # 합성 언어 (ko, ja, en), None이면 글로벌 설정 사용


@router.post("/synthesize")
async def synthesize(request: SynthesizeRequest):
    """텍스트를 음성으로 변환 (WAV 반환)

    char_id가 필수이며, GPT-SoVITS 엔진으로 합성합니다.
    준비되지 않은 캐릭터는 자동으로 참조 오디오를 준비합니다.
    """
    if not request.text:
        raise HTTPException(status_code=400, detail="Text is required")

    if not request.char_id:
        raise HTTPException(status_code=400, detail="char_id is required")

    # 요청 언어 또는 글로벌 설정
    language = request.language or config.gpt_sovits_language

    # GPT-SoVITS 엔진 처리
    try:
        synthesizer = get_gpt_synthesizer()
        model_manager = get_gpt_model_manager()

        # 모델이 준비되어 있는지 확인
        if not model_manager.is_trained(request.char_id, language):
            # 자동으로 참조 오디오 준비 시도
            logger.info(f"캐릭터 준비 중: {request.char_id} (lang={language})")
            from ...common.language_codes import short_to_voice_folder
            voice_folder = short_to_voice_folder(language)
            audio_dir = config.extracted_path / voice_folder / request.char_id
            output_dir = config.models_path / "gpt_sovits" / language / request.char_id

            if not audio_dir.exists():
                raise HTTPException(
                    status_code=404,
                    detail=f"캐릭터 음성 데이터 없음: {request.char_id} ({voice_folder})"
                )

            # 참조 오디오 준비 (동기 실행)
            gpt_config = synthesizer.config
            success = prepare_reference_audio(
                char_id=request.char_id,
                audio_dir=audio_dir,
                output_dir=output_dir,
                gamedata_path=config.gamedata_path,
                language=language,
                min_duration=gpt_config.min_ref_audio_length,
                max_duration=gpt_config.max_ref_audio_length,
            )

            if not success or not model_manager.is_trained(request.char_id, language):
                raise HTTPException(
                    status_code=500,
                    detail=f"GPT-SoVITS 모델 준비 실패: {request.char_id}"
                )

            # 자동 준비 성공 시 config.json 생성
            if not model_manager.get_model_info(request.char_id, language):
                model_manager.create_model_info(
                    char_id=request.char_id,
                    char_name=request.char_id,
                    epochs_sovits=0,
                    epochs_gpt=0,
                    ref_audio_count=len(list(audio_dir.glob("*.mp3"))) + len(list(audio_dir.glob("*.wav"))),
                    language=language,
                )
                logger.info(f"캐릭터 준비 완료 (자동): {request.char_id} (lang={language})")

        logger.info(f"GPT-SoVITS 합성: {request.char_id} (lang={language})")

        # GPT-SoVITS API 서버 연결 확인 (재시도 포함)
        api_running = await synthesizer.api_client.is_api_running()
        if not api_running:
            # 재시도 (서버가 일시적으로 바쁠 수 있음)
            import asyncio
            logger.warning("GPT-SoVITS API 응답 없음, 2초 후 재시도...")
            await asyncio.sleep(2)
            api_running = await synthesizer.api_client.is_api_running()

        if not api_running:
            # 상세 진단 정보 로깅
            status = synthesizer.api_client.get_api_status()
            logger.error(f"GPT-SoVITS API 연결 실패: {status}")
            raise HTTPException(
                status_code=503,
                detail=f"GPT-SoVITS API 서버가 응답하지 않습니다. 상태: {status}"
            )

        # GPU 세마포어: OCR과 동시 실행 방지 (메모리 부족 크래시 방지)
        async with gpu_semaphore_context():
            logger.info(f"GPU 세마포어 통과: {request.char_id}")

            # 모델 로드
            if not await synthesizer.load_model(request.char_id):
                raise HTTPException(
                    status_code=500,
                    detail=f"GPT-SoVITS 모델 로드 실패: {request.char_id}"
                )

            # 합성
            gpt_config = synthesizer.config
            result = await synthesizer.synthesize(
                char_id=request.char_id,
                text=request.text,
                language=language,
                speed_factor=gpt_config.speed_factor,
                top_k=gpt_config.top_k,
                top_p=gpt_config.top_p,
                temperature=gpt_config.temperature,
            )

        if not result:
            raise HTTPException(
                status_code=500,
                detail=f"GPT-SoVITS 음성 합성 실패: {request.char_id}"
            )

        # WAV 파일 읽기
        audio_data = result.audio_path.read_bytes()
        return Response(
            content=audio_data,
            media_type="audio/wav",
            headers={
                "X-Sample-Rate": str(result.sample_rate),
                "X-Duration-Ms": str(result.duration * 1000),
                "X-Provider": "gpt_sovits",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"GPT-SoVITS 오류: {e}")
        raise HTTPException(status_code=500, detail=f"GPT-SoVITS 오류: {str(e)}")


@router.get("/gpt-sovits/status")
async def gpt_sovits_status():
    """GPT-SoVITS 상태 확인"""
    try:
        synthesizer = get_gpt_synthesizer()
        model_manager = get_gpt_model_manager()

        # 합성 중이면 health check 스킵 (단일 스레드 서버라 응답 못함)
        is_synthesizing = synthesizer.is_synthesizing
        if is_synthesizing:
            api_running = True  # 합성 중이므로 실행 중으로 간주
        else:
            api_running = await synthesizer.api_client.is_api_running()

        # 준비된 캐릭터
        ready_chars = model_manager.get_trained_characters()

        return {
            "installed": synthesizer.config.is_gpt_sovits_installed,
            "api_running": api_running,
            "synthesizing": is_synthesizing,  # 합성 진행 중 상태 추가
            "force_zero_shot": synthesizer.force_zero_shot,  # 제로샷 강제 모드
            "ready_characters": ready_chars,
            "ready_count": len(ready_chars),
        }
    except Exception as e:
        return {
            "installed": False,
            "api_running": False,
            "synthesizing": False,
            "ready_characters": [],
            "ready_count": 0,
            "error": str(e),
        }


@router.post("/gpt-sovits/reinit")
async def reinit_gpt_sovits():
    """GPT-SoVITS synthesizer 재초기화 (설치 후 반영용)"""
    global _gpt_synthesizer, _gpt_model_manager
    _gpt_synthesizer = None
    _gpt_model_manager = None
    try:
        synthesizer = get_gpt_synthesizer()
        return {
            "installed": synthesizer.config.is_gpt_sovits_installed,
            "message": "GPT-SoVITS 재초기화 완료",
        }
    except Exception as e:
        return {"installed": False, "message": f"재초기화 실패: {e}"}


@router.post("/gpt-sovits/start")
async def start_gpt_sovits_api():
    """GPT-SoVITS API 서버 시작 (명시적 요청)"""
    try:
        synthesizer = get_gpt_synthesizer()
        api_client = synthesizer.api_client

        # 이미 실행 중인지 확인
        if await api_client.is_api_running():
            return {"status": "running", "message": "GPT-SoVITS API 서버가 이미 실행 중입니다"}

        # GPT-SoVITS 설치 확인
        if not synthesizer.config.is_gpt_sovits_installed:
            raise HTTPException(
                status_code=400,
                detail=f"GPT-SoVITS가 설치되어 있지 않습니다: {synthesizer.config.gpt_sovits_path}"
            )

        # API 서버 시작
        if not api_client.start_api_server():
            # 상세 진단 정보 반환
            status = api_client.get_api_status()
            raise HTTPException(
                status_code=500,
                detail=f"GPT-SoVITS API 서버 시작 실패. 진단: {status}"
            )

        # 준비될 때까지 대기
        if await api_client.wait_for_api_ready(timeout=60.0):
            return {"status": "running", "message": "GPT-SoVITS API 서버가 시작되었습니다"}
        else:
            # 프로세스 상태 확인
            status = api_client.get_api_status()
            raise HTTPException(
                status_code=500,
                detail=f"GPT-SoVITS API 서버 준비 시간 초과 (60초). 진단: {status}"
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/gpt-sovits/diagnose")
async def diagnose_gpt_sovits():
    """GPT-SoVITS 상세 진단 정보"""
    try:
        synthesizer = get_gpt_synthesizer()
        api_client = synthesizer.api_client
        config = synthesizer.config

        # 기본 정보
        diagnosis = {
            "config": {
                "gpt_sovits_path": str(config.gpt_sovits_path),
                "gpt_sovits_path_exists": config.gpt_sovits_path.exists(),
                "python_path": str(config.python_path) if config.python_path else None,
                "python_exists": config.python_path.exists() if config.python_path else False,
                "api_url": config.api_url,
            },
            "installation": {
                "is_installed": config.is_gpt_sovits_installed,
            },
            "api_status": api_client.get_api_status(),
            "api_reachable": await api_client.is_api_running(),
        }

        # API 스크립트 확인
        api_v2 = config.gpt_sovits_path / "api_v2.py"
        api_v1 = config.gpt_sovits_path / "api.py"
        diagnosis["installation"]["api_v2_exists"] = api_v2.exists()
        diagnosis["installation"]["api_v1_exists"] = api_v1.exists()

        # runtime 디렉토리 확인
        runtime_dir = config.gpt_sovits_path / "runtime"
        diagnosis["installation"]["runtime_dir_exists"] = runtime_dir.exists()
        if runtime_dir.exists():
            python_exe = runtime_dir / "python.exe"
            diagnosis["installation"]["runtime_python_exists"] = python_exe.exists()

        # 필수 파일 확인
        critical_files = [
            "GPT_SoVITS",
            "GPT_weights",
            "SoVITS_weights",
            "pretrained_models",
        ]
        diagnosis["installation"]["critical_dirs"] = {}
        for name in critical_files:
            path = config.gpt_sovits_path / name
            diagnosis["installation"]["critical_dirs"][name] = path.exists()

        return diagnosis

    except Exception as e:
        logger.exception("진단 중 오류")
        return {
            "error": str(e),
            "error_type": type(e).__name__,
        }


@router.get("/gpt-sovits/force-zero-shot")
async def get_force_zero_shot():
    """제로샷 강제 모드 상태 조회

    True면 학습된 모델이 있어도 제로샷 모드로 동작합니다.
    """
    synthesizer = get_gpt_synthesizer()
    return {
        "force_zero_shot": synthesizer.force_zero_shot,
    }


@router.post("/gpt-sovits/force-zero-shot")
async def set_force_zero_shot(enabled: bool = True):
    """제로샷 강제 모드 토글

    True로 설정하면 학습된 모델이 있어도 제로샷 모드로 동작합니다.
    테스트/품질 비교용으로 사용합니다.
    """
    synthesizer = get_gpt_synthesizer()
    synthesizer.set_force_zero_shot(enabled)
    return {
        "force_zero_shot": synthesizer.force_zero_shot,
        "message": f"제로샷 강제 모드가 {'활성화' if enabled else '비활성화'}되었습니다",
    }


class TTSParamsResponse(BaseModel):
    """TTS 추론 파라미터"""
    speed_factor: float
    top_k: int
    top_p: float
    temperature: float


class UpdateTTSParamsRequest(BaseModel):
    """TTS 추론 파라미터 업데이트 요청"""
    speed_factor: Optional[float] = None
    top_k: Optional[int] = None
    top_p: Optional[float] = None
    temperature: Optional[float] = None


@router.get("/gpt-sovits/tts-params")
async def get_tts_params():
    """TTS 추론 파라미터 조회"""
    synthesizer = get_gpt_synthesizer()
    c = synthesizer.config
    return TTSParamsResponse(
        speed_factor=c.speed_factor,
        top_k=c.top_k,
        top_p=c.top_p,
        temperature=c.temperature,
    )


@router.put("/gpt-sovits/tts-params")
async def update_tts_params(request: UpdateTTSParamsRequest):
    """TTS 추론 파라미터 업데이트

    변경한 값만 전송하면 됩니다. 변경 즉시 이후 TTS 합성에 적용됩니다.
    """
    synthesizer = get_gpt_synthesizer()
    c = synthesizer.config

    if request.speed_factor is not None:
        if not (0.5 <= request.speed_factor <= 2.0):
            raise HTTPException(status_code=400, detail="speed_factor는 0.5~2.0 범위여야 합니다")
        c.speed_factor = request.speed_factor

    if request.top_k is not None:
        if not (1 <= request.top_k <= 30):
            raise HTTPException(status_code=400, detail="top_k는 1~30 범위여야 합니다")
        c.top_k = request.top_k

    if request.top_p is not None:
        if not (0.1 <= request.top_p <= 1.0):
            raise HTTPException(status_code=400, detail="top_p는 0.1~1.0 범위여야 합니다")
        c.top_p = request.top_p

    if request.temperature is not None:
        if not (0.1 <= request.temperature <= 2.0):
            raise HTTPException(status_code=400, detail="temperature는 0.1~2.0 범위여야 합니다")
        c.temperature = request.temperature

    return TTSParamsResponse(
        speed_factor=c.speed_factor,
        top_k=c.top_k,
        top_p=c.top_p,
        temperature=c.temperature,
    )
