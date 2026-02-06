"""별칭 관리 API 라우터"""

import json
import logging
import re
from collections import defaultdict
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...character.official_data import get_official_data_provider
from ..config import config

logger = logging.getLogger(__name__)
router = APIRouter()


class AliasInfo(BaseModel):
    """별칭 정보"""

    alias: str
    char_id: str


class AliasCreateRequest(BaseModel):
    """별칭 추가 요청"""

    alias: str
    char_id: str


class CharacterAliasesResponse(BaseModel):
    """캐릭터의 별칭 목록 응답"""

    char_id: str
    aliases: list[str]


@router.get("")
async def list_aliases():
    """전체 별칭 목록 조회"""
    provider = get_official_data_provider()
    aliases = provider.get_all_aliases()

    return {
        "total": len(aliases),
        "aliases": [
            AliasInfo(alias=alias, char_id=char_id)
            for alias, char_id in sorted(aliases.items())
        ],
    }


@router.get("/search")
async def search_by_alias(q: str):
    """별칭으로 캐릭터 검색

    Args:
        q: 검색어 (별칭)
    """
    if not q or len(q) < 1:
        raise HTTPException(status_code=400, detail="검색어를 입력하세요")

    provider = get_official_data_provider()
    char_id = provider.get_char_id_by_name(q)

    if char_id:
        # 캐릭터 정보 조회
        char_info = provider.get_char_info(char_id)
        codename = char_info.get("name", "") if char_info else ""

        return {
            "found": True,
            "query": q,
            "char_id": char_id,
            "codename": codename,
        }
    else:
        return {
            "found": False,
            "query": q,
            "char_id": None,
            "codename": None,
        }


@router.get("/character/{char_id}")
async def get_character_aliases(char_id: str):
    """특정 캐릭터의 모든 별칭 조회"""
    provider = get_official_data_provider()
    aliases = provider.get_aliases_for_char(char_id)

    # 캐릭터 정보 조회
    char_info = provider.get_char_info(char_id)
    if not char_info and not aliases:
        raise HTTPException(
            status_code=404, detail=f"캐릭터를 찾을 수 없습니다: {char_id}"
        )

    return CharacterAliasesResponse(char_id=char_id, aliases=aliases)


@router.post("")
async def add_alias(request: AliasCreateRequest):
    """별칭 추가"""
    provider = get_official_data_provider()

    # 캐릭터 존재 확인
    char_info = provider.get_char_info(request.char_id)
    if not char_info:
        raise HTTPException(
            status_code=404,
            detail=f"캐릭터를 찾을 수 없습니다: {request.char_id}",
        )

    success = provider.add_alias(request.alias, request.char_id)
    if not success:
        existing = provider.get_all_aliases().get(request.alias)
        raise HTTPException(
            status_code=409,
            detail=f"별칭이 이미 존재합니다: {request.alias} → {existing}",
        )

    codename = char_info.get("name", "")
    return {
        "success": True,
        "alias": request.alias,
        "char_id": request.char_id,
        "codename": codename,
    }


@router.delete("/{alias}")
async def delete_alias(alias: str):
    """별칭 삭제"""
    provider = get_official_data_provider()

    # 기존 매핑 확인
    existing = provider.get_all_aliases().get(alias)
    if not existing:
        raise HTTPException(
            status_code=404, detail=f"별칭을 찾을 수 없습니다: {alias}"
        )

    success = provider.remove_alias(alias)
    if not success:
        raise HTTPException(status_code=500, detail="별칭 삭제 실패")

    return {
        "success": True,
        "alias": alias,
        "char_id": existing,
    }


# ===== 본명 추출 관련 =====

REALNAME_PATTERNS = [
    r"본명은\s+([가-힣a-zA-Z·\-\s]{2,30}?)[,\.。]",
    r"본명은\s+([가-힣a-zA-Z·\-\s]{2,30}?)라고",
    r"본명은\s+([가-힣a-zA-Z·\-\s]{2,30}?)(?:이다|였다)",
    r"본명인\s*'([가-힣a-zA-Z·\-\s]{2,20}?)'",  # 본명인 '글로리아'
    r"본명\s+([가-힣a-zA-Z·\-\s]{2,30}?),",  # 본명 모리우치 토오루,
]

SUFFIXES_TO_REMOVE = ["이다", "였다", "이며", "로서", "로써", "라고", "라는", "란", "다", "로"]


def _clean_realname(realname: str) -> str:
    """본명에서 조사 제거"""
    cleaned = realname.strip()
    for suffix in SUFFIXES_TO_REMOVE:
        if cleaned.endswith(suffix) and len(cleaned) > len(suffix) + 2:
            cleaned = cleaned[: -len(suffix)].strip()
            break
    return cleaned


def _extract_realname_from_text(text: str) -> str | None:
    """텍스트에서 본명 추출"""
    for pattern in REALNAME_PATTERNS:
        match = re.search(pattern, text)
        if match:
            realname = match.group(1).strip()
            realname = _clean_realname(realname)
            if 2 <= len(realname) <= 20:
                return realname
    return None


def _split_name_parts(realname: str) -> list[str]:
    """본명을 부분으로 분리"""
    parts = [realname]
    words = realname.split()
    if len(words) >= 2:
        parts.extend(words)
    if "·" in realname:
        parts.extend(realname.split("·"))
    unique_parts = []
    seen = set()
    for part in parts:
        part = part.strip()
        if part and len(part) >= 2 and part not in seen:
            unique_parts.append(part)
            seen.add(part)
    return unique_parts


@router.post("/extract-realnames")
async def extract_realnames(dry_run: bool = False):
    """handbook에서 본명 추출하여 별칭으로 등록

    Args:
        dry_run: True면 실제 저장 없이 결과만 반환
    """
    gamedata_path = Path(config.data_path) / "gamedata" / "kr" / "gamedata" / "excel"
    handbook_path = gamedata_path / "handbook_info_table.json"
    char_table_path = gamedata_path / "character_table.json"

    if not handbook_path.exists():
        raise HTTPException(status_code=404, detail="handbook_info_table.json을 찾을 수 없습니다")
    if not char_table_path.exists():
        raise HTTPException(status_code=404, detail="character_table.json을 찾을 수 없습니다")

    # 데이터 로드
    with open(handbook_path, "r", encoding="utf-8") as f:
        handbook = json.load(f)
    with open(char_table_path, "r", encoding="utf-8") as f:
        char_table = json.load(f)

    # 본명 추출
    realnames: dict[str, dict] = {}
    handbook_dict = handbook.get("handbookDict", {})

    for char_id, char_data in handbook_dict.items():
        if not char_id.startswith("char_") or "_npc_" in char_id:
            continue

        for audio in char_data.get("storyTextAudio", []):
            for story in audio.get("stories", []):
                text = story.get("storyText", "")
                if "본명" in text:
                    realname = _extract_realname_from_text(text)
                    if realname:
                        codename = char_table.get(char_id, {}).get("name", "")
                        realnames[char_id] = {"realname": realname, "codename": codename}
                        break
            if char_id in realnames:
                break

    # 충돌 체크하여 별칭 생성
    part_to_chars: dict[str, list[str]] = defaultdict(list)
    for char_id, data in realnames.items():
        parts = _split_name_parts(data["realname"])
        for part in parts:
            part_to_chars[part].append(char_id)

    aliases_to_add: dict[str, str] = {}
    conflicts: dict[str, list[str]] = {}
    skipped_same_as_codename: list[str] = []

    for part, char_ids in part_to_chars.items():
        if len(char_ids) == 1:
            char_id = char_ids[0]
            codename = char_table.get(char_id, {}).get("name", "")
            # 콜사인과 동일하면 스킵 (예: 안젤리나 = 안젤리나)
            if part == codename:
                skipped_same_as_codename.append(part)
                continue
            aliases_to_add[part] = char_id
        else:
            conflicts[part] = [char_table.get(cid, {}).get("name", cid) for cid in char_ids]

    # 저장
    if not dry_run:
        provider = get_official_data_provider()
        added_count = 0
        for alias, char_id in aliases_to_add.items():
            if provider.add_alias(alias, char_id):
                added_count += 1

        return {
            "success": True,
            "extracted_count": len(realnames),
            "alias_count": added_count,
            "total_aliases": len(provider.get_all_aliases()),
            "conflicts": conflicts,
            "skipped_same_as_codename": skipped_same_as_codename,
        }
    else:
        return {
            "success": True,
            "dry_run": True,
            "extracted_count": len(realnames),
            "alias_count": len(aliases_to_add),
            "aliases_preview": [
                {"alias": alias, "char_id": char_id, "codename": char_table.get(char_id, {}).get("name", "")}
                for alias, char_id in sorted(aliases_to_add.items())
            ],
            "conflicts": conflicts,
            "skipped_same_as_codename": skipped_same_as_codename,
        }
