"""TTS 관련 라우터"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from ..config import config
from ...voice.providers.edge_tts import EdgeTTSProvider

router = APIRouter()

# 전역 TTS 프로바이더
_tts_provider: EdgeTTSProvider | None = None


def get_tts_provider() -> EdgeTTSProvider:
    global _tts_provider
    if _tts_provider is None:
        _tts_provider = EdgeTTSProvider(default_voice=config.default_voice)
    return _tts_provider


class SynthesizeRequest(BaseModel):
    """TTS 합성 요청"""

    text: str
    voice_id: str | None = None


class SynthesizeResponse(BaseModel):
    """TTS 합성 응답 (메타데이터)"""

    sample_rate: int
    duration_ms: float
    audio_size: int


@router.post("/synthesize")
async def synthesize(request: SynthesizeRequest):
    """텍스트를 음성으로 변환 (MP3 반환)"""
    if not request.text:
        raise HTTPException(status_code=400, detail="Text is required")

    provider = get_tts_provider()
    result = await provider.synthesize(request.text, request.voice_id)

    return Response(
        content=result.audio_data,
        media_type="audio/mpeg",
        headers={
            "X-Sample-Rate": str(result.sample_rate),
            "X-Duration-Ms": str(result.duration_ms),
        },
    )


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
