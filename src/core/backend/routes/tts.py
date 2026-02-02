"""TTS 관련 라우터

Edge TTS (기본) + GPT-SoVITS (캐릭터별 음성 클로닝) 지원
"""

import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from ..config import config
from ...voice.providers.edge_tts import EdgeTTSProvider
from ...voice.gpt_sovits import GPTSoVITSConfig, GPTSoVITSModelManager
from ...voice.gpt_sovits.synthesizer import GPTSoVITSSynthesizer

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
    """TTS 합성 요청"""

    text: str
    voice_id: str | None = None
    char_id: str | None = None  # 캐릭터 ID (GPT-SoVITS용)
    use_gpt_sovits: bool = True  # GPT-SoVITS 사용 여부 (기본 True)


class SynthesizeResponse(BaseModel):
    """TTS 합성 응답 (메타데이터)"""

    sample_rate: int
    duration_ms: float
    audio_size: int


@router.post("/synthesize")
async def synthesize(request: SynthesizeRequest):
    """텍스트를 음성으로 변환 (WAV 반환)

    char_id가 필수이며, GPT-SoVITS로만 합성합니다.
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
            raise HTTPException(
                status_code=404,
                detail=f"GPT-SoVITS 모델이 준비되지 않음: {request.char_id}"
            )

        logger.info(f"GPT-SoVITS 합성: {request.char_id}")

        # 모델 로드
        if not await synthesizer.load_model(request.char_id):
            raise HTTPException(
                status_code=500,
                detail=f"GPT-SoVITS 모델 로드 실패: {request.char_id}"
            )

        # 합성
        result = await synthesizer.synthesize(
            char_id=request.char_id,
            text=request.text,
            language=config.voice_language,
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

        # API 서버 상태
        api_running = await synthesizer.api_client.is_api_running()

        # 준비된 캐릭터
        ready_chars = model_manager.get_trained_characters()

        return {
            "installed": synthesizer.config.is_gpt_sovits_installed,
            "api_running": api_running,
            "ready_characters": ready_chars,
            "ready_count": len(ready_chars),
        }
    except Exception as e:
        return {
            "installed": False,
            "api_running": False,
            "ready_characters": [],
            "ready_count": 0,
            "error": str(e),
        }


@router.post("/gpt-sovits/start")
async def start_gpt_sovits_api():
    """GPT-SoVITS API 서버 시작"""
    try:
        synthesizer = get_gpt_synthesizer()

        if await synthesizer.ensure_api_running():
            return {"status": "running", "message": "GPT-SoVITS API 서버가 실행 중입니다"}
        else:
            raise HTTPException(status_code=500, detail="GPT-SoVITS API 서버 시작 실패")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
