"""음성 자산 관련 라우터"""

import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..config import config
from ...voice.character_mapping import CharacterVoiceMapper
from ...voice.charword_loader import reset_charword_loader
from ...voice.dialogue_stats import DialogueStatsManager
from ...voice.alias_resolver import invalidate_cache as invalidate_alias_cache

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


# === 캐릭터 별칭 관리 ===

_character_aliases_cache: dict[str, str] | None = None


def _get_aliases_path() -> Path:
    """별칭 파일 경로"""
    return Path(config.data_path) / "character_aliases.json"


def _load_aliases() -> dict[str, str]:
    """캐릭터 별칭 로드 (캐시 사용)"""
    global _character_aliases_cache
    if _character_aliases_cache is not None:
        return _character_aliases_cache

    aliases_path = _get_aliases_path()
    if not aliases_path.exists():
        _character_aliases_cache = {}
        return _character_aliases_cache

    try:
        with open(aliases_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            _character_aliases_cache = data.get("aliases", {})
    except Exception as e:
        logger.error(f"별칭 로드 실패: {e}")
        _character_aliases_cache = {}

    return _character_aliases_cache


def _save_aliases(aliases: dict[str, str]) -> None:
    """캐릭터 별칭 저장"""
    global _character_aliases_cache
    aliases_path = _get_aliases_path()

    data = {
        "_comment": "NPC 이름 → 플레이어블 캐릭터 ID 매핑. 같은 인물이지만 이름이 다른 경우 사용",
        "_usage": "캐릭터 관리 UI에서 편집하거나 직접 수정",
        "aliases": aliases,
    }

    try:
        aliases_path.parent.mkdir(parents=True, exist_ok=True)
        with open(aliases_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        _character_aliases_cache = aliases
        logger.info(f"별칭 저장 완료: {len(aliases)}개")
    except Exception as e:
        logger.error(f"별칭 저장 실패: {e}")
        raise HTTPException(status_code=500, detail=f"별칭 저장 실패: {str(e)}")


def _invalidate_aliases_cache() -> None:
    """별칭 캐시 무효화"""
    global _character_aliases_cache
    _character_aliases_cache = None

    # 공통 모듈의 캐시도 무효화
    invalidate_alias_cache()


class AliasInfo(BaseModel):
    """별칭 정보"""
    alias: str  # NPC 이름 (예: "모모카")
    char_id: str  # 플레이어블 캐릭터 ID (예: "char_4202_haruka")


class AddAliasRequest(BaseModel):
    """별칭 추가 요청"""
    alias: str
    char_id: str


@router.get("/aliases")
async def list_aliases():
    """캐릭터 별칭 목록 조회

    Returns:
        aliases: NPC 이름 → 캐릭터 ID 매핑
        aliases_by_char: 캐릭터 ID별 별칭 목록
    """
    aliases = _load_aliases()

    # 캐릭터별 별칭 그룹화
    aliases_by_char: dict[str, list[str]] = {}
    for alias, char_id in aliases.items():
        if char_id not in aliases_by_char:
            aliases_by_char[char_id] = []
        aliases_by_char[char_id].append(alias)

    return {
        "total": len(aliases),
        "aliases": aliases,
        "aliases_by_char": aliases_by_char,
    }


@router.get("/aliases/{char_id}")
async def get_character_aliases(char_id: str):
    """특정 캐릭터의 별칭 목록 조회"""
    aliases = _load_aliases()

    char_aliases = [alias for alias, cid in aliases.items() if cid == char_id]

    return {
        "char_id": char_id,
        "aliases": char_aliases,
    }


@router.post("/aliases")
async def add_alias(request: AddAliasRequest):
    """별칭 추가

    Args:
        alias: NPC 이름 (예: "모모카")
        char_id: 플레이어블 캐릭터 ID (예: "char_4202_haruka")
    """
    aliases = _load_aliases().copy()

    # 이미 존재하는 별칭인지 확인
    if request.alias in aliases:
        existing = aliases[request.alias]
        if existing == request.char_id:
            return {"message": "이미 등록된 별칭입니다", "alias": request.alias}
        raise HTTPException(
            status_code=400,
            detail=f"'{request.alias}'은(는) 이미 '{existing}'에 매핑되어 있습니다",
        )

    aliases[request.alias] = request.char_id
    _save_aliases(aliases)
    _invalidate_aliases_cache()

    return {
        "message": "별칭이 추가되었습니다",
        "alias": request.alias,
        "char_id": request.char_id,
    }


@router.delete("/aliases/{alias}")
async def remove_alias(alias: str):
    """별칭 삭제"""
    aliases = _load_aliases().copy()

    if alias not in aliases:
        raise HTTPException(status_code=404, detail=f"별칭을 찾을 수 없습니다: {alias}")

    char_id = aliases.pop(alias)
    _save_aliases(aliases)
    _invalidate_aliases_cache()

    return {
        "message": "별칭이 삭제되었습니다",
        "alias": alias,
        "char_id": char_id,
    }
