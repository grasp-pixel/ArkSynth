"""음성 자산 관련 라우터"""

import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..config import config
from ..shared_loaders import get_voice_mapper, reset_story_loader, reset_voice_mapper
from ...voice.character_mapping import CharacterVoiceMapper
from ...voice.dialogue_stats import DialogueStatsManager
from ...voice.alias_resolver import invalidate_cache as invalidate_alias_cache
from ...voice.gender_mapper import GenderMapper
from ...voice.character_images import CharacterImageProvider

logger = logging.getLogger(__name__)

router = APIRouter()

# 전역 매퍼 (통계 관리자만 로컬 유지)
_stats_manager: DialogueStatsManager | None = None


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
    mapper = get_voice_mapper()
    stats_manager = get_stats_manager()
    lang = lang or config.voice_language
    characters = mapper.get_available_characters(lang)

    # 대사 통계 로드
    stats = stats_manager.get_stats(config.display_language)

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


@router.get("/characters/search")
async def search_characters(q: str, lang: str | None = None, limit: int = 30):
    """캐릭터 테이블에서 검색 (음성 파일 유무와 무관)

    플레이어블 캐릭터(char_로 시작)를 이름 또는 ID로 검색합니다.
    NPC에 특정 캐릭터 음성을 매핑할 때 사용합니다.

    Args:
        q: 검색어 (이름 또는 char_id)
        lang: 언어 코드
        limit: 최대 결과 수 (기본 30)
    """
    from ..shared_loaders import get_story_loader

    loader = get_story_loader()
    mapper = get_voice_mapper()
    lang = lang or config.display_language
    voice_lang = config.voice_language

    characters = loader.load_characters(lang)
    q_lower = q.lower()

    results = []
    for char_id, char in characters.items():
        # 플레이어블 캐릭터만 (char_로 시작, npc 제외)
        if not char_id.startswith("char_") or char_id.startswith("char_npc_"):
            continue

        name = char.name_ko or char.name or ""

        # 이름 또는 ID에 검색어 포함
        if q_lower in name.lower() or q_lower in char_id.lower():
            has_voice = mapper.has_voice(char_id, voice_lang)
            results.append({
                "char_id": char_id,
                "name": name,
                "has_voice": has_voice,
            })

            if len(results) >= limit:
                break

    return {
        "query": q,
        "total": len(results),
        "characters": results,
    }


@router.get("/characters/{char_id}")
async def get_character_voice_info(char_id: str, lang: str | None = None):
    """특정 캐릭터의 음성 정보"""
    mapper = get_voice_mapper()
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
    mapper = get_voice_mapper()
    lang = lang or config.voice_language
    return mapper.get_voice_summary(lang)


@router.get("/check/{char_id}")
async def check_voice_availability(char_id: str, lang: str | None = None):
    """캐릭터 음성 존재 여부 확인"""
    mapper = get_voice_mapper()
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
    stats = stats_manager.rebuild_stats(config.display_language)

    return {
        "total_characters": len(stats),
        "message": "대사 통계가 재계산되었습니다.",
    }


@router.post("/refresh")
async def refresh_character_data():
    """캐릭터 데이터 새로고침 (게임 데이터 업데이트 후 호출)

    캐릭터 매핑 캐시, 대사 통계, charword 로더, 이미지 프로바이더를 모두 갱신합니다.
    """
    global _stats_manager, _image_provider

    # 공유 로더 리셋 (story_loader + voice_mapper)
    reset_story_loader()
    reset_voice_mapper()

    # 이미지 프로바이더 리셋
    _image_provider = None

    # 대사 통계 재계산 (항상 rebuild 호출)
    if _stats_manager is None:
        _stats_manager = DialogueStatsManager(config.data_path)
    _stats_manager.rebuild_stats(config.display_language)

    # 새로운 캐릭터 목록 가져오기
    mapper = get_voice_mapper()
    voice_info = mapper.scan_voice_folders(config.voice_language)

    return {
        "total_characters": len(voice_info),
        "message": "캐릭터 데이터가 새로고침되었습니다.",
    }


@router.get("/dialogue-stats")
async def get_dialogue_stats():
    """대사 통계 조회"""
    stats_manager = get_stats_manager()
    stats = stats_manager.get_stats(config.display_language)

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
    get_all_voice_mappings_flat,
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
        mappings: 스프라이트 ID → 음성 캐릭터 ID 매핑 (플랫 형식, 프론트엔드 호환)
        mappings_v2: 스프라이트 ID → {voice_char_id, source} (v2 형식, 상세 정보)
        mappings_by_voice: 음성 캐릭터별 스프라이트 ID 목록
    """
    # v2 형식 (상세 정보)
    mappings_v2 = get_all_voice_mappings()

    # 플랫 형식 (프론트엔드 호환)
    mappings = get_all_voice_mappings_flat()

    # 음성 캐릭터별 스프라이트 그룹화
    mappings_by_voice: dict[str, list[str]] = {}
    for sprite_id, voice_char_id in mappings.items():
        if voice_char_id not in mappings_by_voice:
            mappings_by_voice[voice_char_id] = []
        mappings_by_voice[voice_char_id].append(sprite_id)

    return {
        "total": len(mappings),
        "mappings": mappings,  # 플랫 형식 (호환성)
        "mappings_v2": mappings_v2,  # v2 형식 (상세 정보)
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


@router.delete("/voice-mappings/{sprite_id:path}")
async def remove_voice_mapping(sprite_id: str):
    """음성 매핑 삭제

    Note: sprite_id에 name:XXX 형식도 지원 (URL 인코딩 필요)
    """
    # 플랫 형식으로 확인 (name: 접두사 포함)
    mappings = get_all_voice_mappings_flat()

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


def reset_image_provider() -> None:
    """이미지 프로바이더 캐시 리셋"""
    global _image_provider
    _image_provider = None


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
        return Response(status_code=204)

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
