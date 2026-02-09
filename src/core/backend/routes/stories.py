"""스토리 카테고리/그룹 관련 라우터"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..config import config
from ..shared_loaders import get_story_loader, get_voice_mapper, reset_story_loader, find_operator_id_by_name
from ...models.story import StoryCategory

router = APIRouter()


# ========== 응답 모델 ==========


class CategoryInfo(BaseModel):
    """카테고리 정보"""

    id: str
    name: str
    group_count: int
    episode_count: int


class StoryGroupInfo(BaseModel):
    """스토리 그룹 정보"""

    id: str
    name: str
    category: str
    entry_type: str
    episode_count: int


class EpisodeInfo(BaseModel):
    """에피소드 정보"""

    id: str
    story_id: str
    code: str
    name: str
    tag: str
    display_name: str


class GroupCharacterInfo(BaseModel):
    """그룹 내 캐릭터 정보"""

    char_id: str | None  # None이면 나레이터
    name: str
    dialogue_count: int
    has_voice: bool
    voice_char_id: str | None = None  # 실제 음성 파일이 있는 캐릭터 ID (이름 매칭 시)


# ========== 엔드포인트 ==========


@router.get("/categories")
async def list_categories(lang: str | None = None):
    """스토리 카테고리 목록

    각 카테고리별 그룹 수와 에피소드 수를 반환
    """
    loader = get_story_loader()
    lang = lang or config.display_language

    stats = loader.get_category_stats(lang)

    # 카테고리 이름 매핑
    category_names = {
        "mainline": "메인 스토리",
        "event": "이벤트 스토리",
        "side": "사이드 스토리",
        "mini": "미니 스토리",
        "other": "기타",
    }

    categories = []
    for cat_id, info in stats.items():
        # other 카테고리는 UI에서 숨김 (튜토리얼, 시스템 등)
        if cat_id == "other":
            continue

        categories.append(
            CategoryInfo(
                id=cat_id,
                name=category_names.get(cat_id, cat_id),
                group_count=info["group_count"],
                episode_count=info["episode_count"],
            )
        )

    # 메인 > 이벤트 > 사이드 > 미니 순
    order = {"mainline": 0, "event": 1, "side": 2, "mini": 3}
    categories.sort(key=lambda c: order.get(c.id, 99))

    return {"categories": categories, "language": lang}


@router.get("/categories/{category_id}/groups")
async def list_category_groups(category_id: str, lang: str | None = None):
    """카테고리별 스토리 그룹 목록"""
    loader = get_story_loader()
    lang = lang or config.display_language

    # 카테고리 ID -> StoryCategory enum
    try:
        category = StoryCategory(category_id)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid category: {category_id}")

    groups = loader.list_groups_by_category(category, lang)

    return {
        "category": category_id,
        "total": len(groups),
        "groups": [
            StoryGroupInfo(
                id=g.id,
                name=g.name,
                category=g.category.value,
                entry_type=g.entry_type,
                episode_count=g.episode_count,
            )
            for g in groups
        ],
    }


@router.get("/groups/{group_id}/episodes")
async def list_group_episodes(group_id: str, lang: str | None = None):
    """스토리 그룹의 에피소드 목록"""
    loader = get_story_loader()
    lang = lang or config.display_language

    # 그룹 존재 확인
    all_groups = loader.load_all_story_groups(lang)
    if group_id not in all_groups:
        raise HTTPException(status_code=404, detail=f"Group not found: {group_id}")

    group = all_groups[group_id]
    episodes = loader.list_episodes_by_group(group_id, lang)

    return {
        "group_id": group_id,
        "group_name": group.name,
        "category": group.category.value,
        "total": len(episodes),
        "episodes": [
            EpisodeInfo(
                id=ep["id"],
                story_id=ep["story_id"],
                code=ep["code"],
                name=ep["name"],
                tag=ep["tag"],
                display_name=f"{ep['code']} {ep['name']}" if ep["code"] else ep["name"],
            )
            for ep in episodes
        ],
    }


@router.get("/groups/{group_id}/characters")
async def list_group_characters(group_id: str, lang: str | None = None):
    """스토리 그룹의 모든 캐릭터 목록 (음성 보유 여부 포함)

    그룹 내 모든 에피소드를 파싱하여 등장 캐릭터와 대사 수를 집계합니다.
    """
    loader = get_story_loader()
    voice_mapper = get_voice_mapper()
    lang = lang or config.display_language

    # 그룹 존재 확인
    all_groups = loader.load_all_story_groups(lang)
    if group_id not in all_groups:
        raise HTTPException(status_code=404, detail=f"Group not found: {group_id}")

    group = all_groups[group_id]

    # 캐릭터 목록 수집
    characters = loader.get_group_characters(group_id, lang)

    # 음성 보유 여부 확인 (모든 이름 변형으로 검색)
    result = []
    narration_count = 0

    for char_info in characters:
        char_id = char_info["char_id"]
        char_name = char_info["name"]
        names = char_info.get("names", [char_name])
        voice_char_id = None

        # 나레이터는 별도 처리
        if char_id is None and char_name == "나레이터":
            narration_count = char_info["dialogue_count"]
            continue

        # 1. char_id로 음성 확인
        has_voice = voice_mapper.has_voice(char_id) if char_id else False
        if has_voice:
            voice_char_id = char_id

        # 2. 없으면 모든 이름 변형으로 오퍼레이터 ID 찾아서 음성 확인
        if not has_voice:
            for name in names:
                if name:
                    operator_id = find_operator_id_by_name(loader, name, lang)
                    if operator_id and voice_mapper.has_voice(operator_id):
                        has_voice = True
                        voice_char_id = operator_id
                        break

        result.append(
            GroupCharacterInfo(
                char_id=char_id,
                name=char_name,
                dialogue_count=char_info["dialogue_count"],
                has_voice=has_voice,
                voice_char_id=voice_char_id,
            )
        )

    result.sort(key=lambda c: c.dialogue_count, reverse=True)

    return {
        "group_id": group_id,
        "group_name": group.name,
        "total": len(result),
        "characters": result,
        "narration_count": narration_count,
    }
