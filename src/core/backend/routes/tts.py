"""TTS 관련 라우터

GPT-SoVITS 캐릭터별 음성 클로닝 지원
"""

import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from ..config import config
from .. import get_gpu_semaphore
from ...voice.providers.edge_tts import EdgeTTSProvider
from ...voice.gpt_sovits import GPTSoVITSConfig, GPTSoVITSModelManager
from ...voice.gpt_sovits.synthesizer import GPTSoVITSSynthesizer
from ...voice.gpt_sovits.training_worker import prepare_reference_audio

logger = logging.getLogger(__name__)
router = APIRouter()

# 전역 프로바이더
_tts_provider: EdgeTTSProvider | None = None
_gpt_synthesizer: GPTSoVITSSynthesizer | None = None
_gpt_model_manager: GPTSoVITSModelManager | None = None


def get_tts_provider() -> EdgeTTSProvider:
    global _tts_provider
    if _tts_provider is None:
        _tts_provider = EdgeTTSProvider(default_voice=config.default_voice)
    return _tts_provider


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
    char_id: str | None = None  # 캐릭터 ID (GPT-SoVITS용)


class SynthesizeResponse(BaseModel):
    """TTS 합성 응답 (메타데이터)"""

    sample_rate: int
    duration_ms: float
    audio_size: int


@router.post("/synthesize")
async def synthesize(request: SynthesizeRequest):
    """텍스트를 음성으로 변환 (WAV 반환)

    char_id가 필수이며, GPT-SoVITS로만 합성합니다.
    준비되지 않은 캐릭터는 자동으로 참조 오디오를 준비합니다.
    """
    if not request.text:
        raise HTTPException(status_code=400, detail="Text is required")

    if not request.char_id:
        raise HTTPException(status_code=400, detail="char_id is required for GPT-SoVITS")

    try:
        synthesizer = get_gpt_synthesizer()
        model_manager = get_gpt_model_manager()

        # 모델이 준비되어 있는지 확인
        if not model_manager.is_trained(request.char_id):
            # 자동으로 참조 오디오 준비 시도
            logger.info(f"캐릭터 준비 중: {request.char_id}")
            audio_dir = config.extracted_path / request.char_id
            output_dir = config.models_path / "gpt_sovits" / request.char_id
            gamedata_path = Path("data/gamedata_yostar")

            if not audio_dir.exists():
                raise HTTPException(
                    status_code=404,
                    detail=f"캐릭터 음성 데이터 없음: {request.char_id}"
                )

            # 참조 오디오 준비 (동기 실행)
            # GPTSoVITSConfig의 참조 오디오 길이 설정 사용
            gpt_config = synthesizer.config
            success = prepare_reference_audio(
                char_id=request.char_id,
                audio_dir=audio_dir,
                output_dir=output_dir,
                gamedata_path=gamedata_path,
                language=config.gpt_sovits_language,
                min_duration=gpt_config.min_ref_audio_length,
                max_duration=gpt_config.max_ref_audio_length,
            )

            if not success or not model_manager.is_trained(request.char_id):
                raise HTTPException(
                    status_code=500,
                    detail=f"GPT-SoVITS 모델 준비 실패: {request.char_id}"
                )

            # 자동 준비 성공 시 config.json 생성 (list_all_models에 포함되도록)
            if not model_manager.get_model_info(request.char_id):
                model_manager.create_model_info(
                    char_id=request.char_id,
                    char_name=request.char_id,  # 기본값으로 char_id 사용
                    epochs_sovits=0,
                    epochs_gpt=0,
                    ref_audio_count=len(list(audio_dir.glob("*.mp3"))) + len(list(audio_dir.glob("*.wav"))),
                    language=config.gpt_sovits_language,
                )
                logger.info(f"캐릭터 준비 완료 (자동): {request.char_id}")

        logger.info(f"GPT-SoVITS 합성: {request.char_id}")

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
        gpu_sem = get_gpu_semaphore()
        async with gpu_sem:
            logger.info(f"GPU 세마포어 획득: {request.char_id}")

            # 모델 로드
            if not await synthesizer.load_model(request.char_id):
                raise HTTPException(
                    status_code=500,
                    detail=f"GPT-SoVITS 모델 로드 실패: {request.char_id}"
                )

            # 합성 (GPTSoVITSConfig의 기본값 사용)
            gpt_config = synthesizer.config
            result = await synthesizer.synthesize(
                char_id=request.char_id,
                text=request.text,
                language=config.gpt_sovits_language,
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
                "X-Provider": "gpt-sovits",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"GPT-SoVITS 오류: {e}")
        raise HTTPException(status_code=500, detail=f"GPT-SoVITS 오류: {str(e)}")


@router.post("/synthesize/metadata")
async def synthesize_metadata(request: SynthesizeRequest):
    """텍스트를 음성으로 변환하고 메타데이터만 반환"""
    if not request.text:
        raise HTTPException(status_code=400, detail="Text is required")

    provider = get_tts_provider()
    result = await provider.synthesize(request.text, request.voice_id)

    return SynthesizeResponse(
        sample_rate=result.sample_rate,
        duration_ms=result.duration_ms,
        audio_size=len(result.audio_data),
    )


@router.get("/voices")
async def list_voices():
    """사용 가능한 음성 목록"""
    provider = get_tts_provider()
    voices = provider.get_available_voices()

    return {
        "default": config.default_voice,
        "voices": voices,
    }


@router.get("/voices/all")
async def list_all_voices():
    """Edge TTS에서 사용 가능한 모든 음성 목록"""
    voices = await EdgeTTSProvider.list_all_voices()

    # 언어별로 그룹화
    by_language = {}
    for voice in voices:
        locale = voice.get("Locale", "unknown")
        if locale not in by_language:
            by_language[locale] = []
        by_language[locale].append(
            {
                "name": voice.get("ShortName"),
                "gender": voice.get("Gender"),
                "friendly_name": voice.get("FriendlyName"),
            }
        )

    return by_language


@router.get("/voices/{language}")
async def list_voices_by_language(language: str):
    """특정 언어의 음성 목록

    Args:
        language: 언어 코드 (ko-KR, zh-CN, ja-JP, en-US 등)
    """
    voices = await EdgeTTSProvider.list_voices_by_language(language)

    return {
        "language": language,
        "voices": [
            {
                "name": v.get("ShortName"),
                "gender": v.get("Gender"),
                "friendly_name": v.get("FriendlyName"),
            }
            for v in voices
        ],
    }


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
