"""음성 자산 관련 라우터"""

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..config import config
from ...voice.character_mapping import CharacterVoiceMapper
from ...voice.dialogue_stats import DialogueStatsManager

router = APIRouter()

# 전역 매퍼
_mapper: CharacterVoiceMapper | None = None
_stats_manager: DialogueStatsManager | None = None


def get_mapper() -> CharacterVoiceMapper:
    global _mapper
    if _mapper is None:
        _mapper = CharacterVoiceMapper(
            extracted_path=config.extracted_path,
            gamedata_path=config.gamedata_yostar_path,
        )
    return _mapper


def get_stats_manager() -> DialogueStatsManager:
    global _stats_manager
    if _stats_manager is None:
        _stats_manager = DialogueStatsManager(config.data_path)
    return _stats_manager


class CharacterVoiceInfo(BaseModel):
    """캐릭터 음성 정보"""

    char_id: str
    name: str
    file_count: int
    has_voice: bool
    dialogue_count: Optional[int] = None  # 전체 스토리 기준 대사 수


@router.get("/characters")
async def list_voice_characters(lang: str = "voice"):
    """음성이 있는 캐릭터 목록 (대사 수 포함)"""
    mapper = get_mapper()
    stats_manager = get_stats_manager()
    characters = mapper.get_available_characters(lang)

    # 대사 통계 로드
    stats = stats_manager.get_stats(config.game_language)

    result = []
    for char_id in characters:
        name = mapper.get_character_name(char_id, game_lang=config.game_language)
        files = mapper.get_voice_files(char_id, lang)
        dialogue_count = stats[char_id].dialogue_count if char_id in stats else 0

        result.append(
            CharacterVoiceInfo(
                char_id=char_id,
                name=name,
                file_count=len(files),
                has_voice=True,
                dialogue_count=dialogue_count,
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

    name = mapper.get_character_name(char_id, game_lang=config.game_language)
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


@router.post("/dialogue-stats/rebuild")
async def rebuild_dialogue_stats():
    """대사 통계 재계산 (캐시 갱신)"""
    stats_manager = get_stats_manager()
    stats = stats_manager.rebuild_stats(config.game_language)

    return {
        "total_characters": len(stats),
        "message": "대사 통계가 재계산되었습니다.",
    }


@router.get("/dialogue-stats")
async def get_dialogue_stats():
    """대사 통계 조회"""
    stats_manager = get_stats_manager()
    stats = stats_manager.get_stats(config.game_language)

    # 대사 수 기준 상위 20개
    sorted_stats = sorted(
        stats.values(), key=lambda s: s.dialogue_count, reverse=True
    )[:20]

    return {
        "total_characters": len(stats),
        "top_characters": [
            {
                "char_id": s.char_id,
                "dialogue_count": s.dialogue_count,
                "episode_count": s.episode_count,
            }
            for s in sorted_stats
        ],
    }
