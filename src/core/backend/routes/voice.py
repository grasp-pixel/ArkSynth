"""음성 자산 관련 라우터"""

import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..config import config
from ...voice.character_mapping import CharacterVoiceMapper
from ...voice.charword_loader import reset_charword_loader
from ...voice.dialogue_stats import DialogueStatsManager
from ...voice.alias_resolver import invalidate_cache as invalidate_alias_cache
from ...voice.gender_mapper import GenderMapper
from ...voice.character_images import CharacterImageProvider
from .stories import reset_story_loader
from .episodes import reset_episode_loader

logger = logging.getLogger(__name__)

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
async def list_voice_characters(lang: str | None = None):
    """음성이 있는 캐릭터 목록 (대사 수 포함)"""
    mapper = get_mapper()
    stats_manager = get_stats_manager()
    lang = lang or config.voice_language
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
async def get_character_voice_info(char_id: str, lang: str | None = None):
    """특정 캐릭터의 음성 정보"""
    mapper = get_mapper()
    lang = lang or config.voice_language

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
async def get_voice_summary(lang: str | None = None):
    """음성 데이터 요약 정보"""
    mapper = get_mapper()
    lang = lang or config.voice_language
    return mapper.get_voice_summary(lang)


@router.get("/check/{char_id}")
async def check_voice_availability(char_id: str, lang: str | None = None):
    """캐릭터 음성 존재 여부 확인"""
    mapper = get_mapper()
    lang = lang or config.voice_language
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


@router.post("/refresh")
async def refresh_character_data():
    """캐릭터 데이터 새로고침 (게임 데이터 업데이트 후 호출)

    캐릭터 매핑 캐시, 대사 통계, charword 로더를 모두 갱신합니다.
    """
    global _mapper, _stats_manager

    # 매퍼 캐시 초기화 및 재생성
    if _mapper:
        _mapper.clear_cache()
    _mapper = CharacterVoiceMapper(
        extracted_path=config.extracted_path,
        gamedata_path=config.gamedata_yostar_path,
    )

    # charword 로더 캐시 리셋
    reset_charword_loader()

    # 스토리 로더 리셋 (stories.py + episodes.py 모두)
    reset_story_loader()
    reset_episode_loader()

    # 대사 통계 재계산 (항상 rebuild 호출)
    if _stats_manager is None:
        _stats_manager = DialogueStatsManager(config.data_path)
    _stats_manager.rebuild_stats(config.game_language)

    # 새로운 캐릭터 목록 가져오기
    voice_info = _mapper.scan_voice_folders(config.voice_language)

    return {
        "total_characters": len(voice_info),
        "message": "캐릭터 데이터가 새로고침되었습니다.",
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


# === 음성 매핑 관리 (스프라이트 ID → 음성 캐릭터 ID) ===

from ...voice.alias_resolver import (
    get_all_voice_mappings,
    save_voice_mapping,
    delete_voice_mapping,
)


class VoiceMappingInfo(BaseModel):
    """음성 매핑 정보"""
    sprite_id: str  # 스프라이트 ID (예: "avg_npc_109")
    voice_char_id: str  # 음성 캐릭터 ID (예: "char_002_amiya")


class AddVoiceMappingRequest(BaseModel):
    """음성 매핑 추가 요청"""
    sprite_id: str
    voice_char_id: str


@router.get("/voice-mappings")
async def list_voice_mappings():
    """음성 매핑 목록 조회

    Returns:
        mappings: 스프라이트 ID → 음성 캐릭터 ID 매핑
        mappings_by_voice: 음성 캐릭터별 스프라이트 ID 목록
    """
    mappings = get_all_voice_mappings()

    # 음성 캐릭터별 스프라이트 그룹화
    mappings_by_voice: dict[str, list[str]] = {}
    for sprite_id, voice_char_id in mappings.items():
        if voice_char_id not in mappings_by_voice:
            mappings_by_voice[voice_char_id] = []
        mappings_by_voice[voice_char_id].append(sprite_id)

    return {
        "total": len(mappings),
        "mappings": mappings,
        "mappings_by_voice": mappings_by_voice,
    }


@router.get("/voice-mappings/{voice_char_id}")
async def get_voice_mapping_by_char(voice_char_id: str):
    """특정 음성 캐릭터에 매핑된 스프라이트 목록 조회"""
    mappings = get_all_voice_mappings()

    sprite_ids = [sid for sid, vid in mappings.items() if vid == voice_char_id]

    return {
        "voice_char_id": voice_char_id,
        "sprite_ids": sprite_ids,
    }


@router.post("/voice-mappings")
async def add_voice_mapping(request: AddVoiceMappingRequest):
    """음성 매핑 추가

    Args:
        sprite_id: 스프라이트 ID (예: "avg_npc_109")
        voice_char_id: 음성 캐릭터 ID (예: "char_002_amiya")
    """
    mappings = get_all_voice_mappings()

    # 이미 존재하는 매핑인지 확인
    if request.sprite_id in mappings:
        existing = mappings[request.sprite_id]
        if existing == request.voice_char_id:
            return {"message": "이미 등록된 매핑입니다", "sprite_id": request.sprite_id}
        # 기존 매핑 업데이트
        logger.info(f"음성 매핑 업데이트: {request.sprite_id}: {existing} → {request.voice_char_id}")

    success = save_voice_mapping(request.sprite_id, request.voice_char_id)
    if not success:
        raise HTTPException(status_code=500, detail="음성 매핑 저장 실패")

    return {
        "message": "음성 매핑이 추가되었습니다",
        "sprite_id": request.sprite_id,
        "voice_char_id": request.voice_char_id,
    }


@router.delete("/voice-mappings/{sprite_id}")
async def remove_voice_mapping(sprite_id: str):
    """음성 매핑 삭제"""
    mappings = get_all_voice_mappings()

    if sprite_id not in mappings:
        raise HTTPException(status_code=404, detail=f"매핑을 찾을 수 없습니다: {sprite_id}")

    voice_char_id = mappings[sprite_id]
    success = delete_voice_mapping(sprite_id)
    if not success:
        raise HTTPException(status_code=500, detail="음성 매핑 삭제 실패")

    return {
        "message": "음성 매핑이 삭제되었습니다",
        "sprite_id": sprite_id,
        "voice_char_id": voice_char_id,
    }


# === 하위 호환성: 기존 /aliases 엔드포인트 유지 (deprecated) ===
# 새로운 시스템은 스프라이트 ID 기반이므로 화자 이름 기반 별칭은 더 이상 사용하지 않음
# 프론트엔드 호환성을 위해 빈 데이터 반환


@router.get("/aliases")
async def list_aliases():
    """[Deprecated] 화자 이름 별칭 목록 - 스프라이트 ID 기반 시스템으로 대체됨

    새로운 시스템에서는 화자 이름 기반 매핑이 없으므로 빈 데이터를 반환합니다.
    음성 매핑은 /voice-mappings 엔드포인트를 사용하세요.
    """
    return {
        "total": 0,
        "aliases": {},
        "aliases_by_char": {},
    }


@router.post("/aliases")
async def add_alias_legacy(alias: str, char_id: str):
    """[Deprecated] 화자 이름 별칭 추가 - 더 이상 지원하지 않음"""
    raise HTTPException(
        status_code=410,
        detail="화자 이름 기반 별칭은 더 이상 지원하지 않습니다. 스프라이트 ID 기반 /voice-mappings를 사용하세요."
    )


# === 캐릭터 성별/이미지 ===

_gender_mapper: GenderMapper | None = None
_image_provider: CharacterImageProvider | None = None


def get_gender_mapper() -> GenderMapper:
    global _gender_mapper
    if _gender_mapper is None:
        _gender_mapper = GenderMapper(config.gamedata_path)
    return _gender_mapper


def get_image_provider() -> CharacterImageProvider:
    global _image_provider
    if _image_provider is None:
        _image_provider = CharacterImageProvider()
    return _image_provider


@router.get("/genders")
async def list_character_genders():
    """모든 캐릭터 성별 목록"""
    gender_mapper = get_gender_mapper()
    genders = gender_mapper.load_genders()

    return {
        "total": len(genders),
        "genders": genders,
    }


@router.get("/characters/{char_id}/gender")
async def get_character_gender(char_id: str):
    """캐릭터 성별 조회"""
    gender_mapper = get_gender_mapper()
    gender = gender_mapper.get_gender(char_id)

    return {
        "char_id": char_id,
        "gender": gender,
    }


@router.get("/images")
async def list_character_images():
    """캐릭터 이미지 목록 (로컬 추출 이미지)"""
    image_provider = get_image_provider()
    char_ids = image_provider.get_char_ids()

    # 로컬 API URL로 반환
    images = {
        char_id: f"/api/voice/images/{char_id}"
        for char_id in char_ids
    }

    return {
        "total": image_provider.get_image_count(),
        "folders": image_provider.get_folder_count(),
        "characters": len(char_ids),
        "images": images,
    }


@router.get("/images/status")
async def get_image_status():
    """이미지 상태 조회"""
    image_provider = get_image_provider()

    return {
        "total_images": image_provider.get_image_count(),
        "total_folders": image_provider.get_folder_count(),
        "path": str(image_provider.extracted_path),
    }


@router.get("/images/{char_id}")
async def get_character_image(char_id: str):
    """캐릭터 이미지 제공"""
    image_provider = get_image_provider()
    file_path = image_provider.get_image(char_id)

    if not file_path:
        raise HTTPException(status_code=404, detail=f"이미지 없음: {char_id}")

    return FileResponse(
        file_path,
        media_type="image/png",
        filename=f"{char_id}.png",
    )


# === 하위 호환성 (portraits → images) ===


@router.get("/portraits")
async def list_character_portraits():
    """스탠딩 이미지 목록 (하위 호환성)"""
    return await list_character_images()


@router.get("/portraits/{char_id}")
async def get_portrait_image(char_id: str):
    """캐릭터 스탠딩 이미지 제공 (하위 호환성)"""
    return await get_character_image(char_id)
