"""별칭 관리 API 라우터"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...character.official_data import get_official_data_provider

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
