"""음성 자산 관련 라우터"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..config import config
from ...voice.character_mapping import CharacterVoiceMapper

router = APIRouter()

# 전역 매퍼
_mapper: CharacterVoiceMapper | None = None


def get_mapper() -> CharacterVoiceMapper:
    global _mapper
    if _mapper is None:
        _mapper = CharacterVoiceMapper(
            extracted_path=config.extracted_path,
            gamedata_path=config.gamedata_path,
        )
    return _mapper


class CharacterVoiceInfo(BaseModel):
    """캐릭터 음성 정보"""

    char_id: str
    name: str
    file_count: int
    has_voice: bool


@router.get("/characters")
async def list_voice_characters(lang: str = "voice"):
    """음성이 있는 캐릭터 목록"""
    mapper = get_mapper()
    characters = mapper.get_available_characters(lang)

    result = []
    for char_id in characters:
        name = mapper.get_character_name(char_id)
        files = mapper.get_voice_files(char_id, lang)
        result.append(
            CharacterVoiceInfo(
                char_id=char_id,
                name=name,
                file_count=len(files),
                has_voice=True,
            )
        )

    return {
        "total": len(result),
        "characters": result,
    }


@router.get("/characters/{char_id}")
async def get_character_voice_info(char_id: str, lang: str = "voice"):
    """특정 캐릭터의 음성 정보"""
    mapper = get_mapper()

    if not mapper.has_voice(char_id, lang):
        raise HTTPException(
            status_code=404, detail=f"No voice found for character: {char_id}"
        )

    name = mapper.get_character_name(char_id)
    files = mapper.get_voice_files(char_id, lang)

    return {
        "char_id": char_id,
        "name": name,
        "file_count": len(files),
        "files": [str(f.name) for f in files],
    }


@router.get("/summary")
async def get_voice_summary(lang: str = "voice"):
    """음성 데이터 요약 정보"""
    mapper = get_mapper()
    return mapper.get_voice_summary(lang)


@router.get("/check/{char_id}")
async def check_voice_availability(char_id: str, lang: str = "voice"):
    """캐릭터 음성 존재 여부 확인"""
    mapper = get_mapper()
    has_voice = mapper.has_voice(char_id, lang)

    return {
        "char_id": char_id,
        "has_voice": has_voice,
    }
