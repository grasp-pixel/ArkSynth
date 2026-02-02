"""스토리 카테고리/그룹 관련 라우터"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..config import config
from ...models.story import StoryCategory
from ...story.loader import StoryLoader

router = APIRouter()

# 전역 로더 (lazy init)
_loader: StoryLoader | None = None


def get_loader() -> StoryLoader:
    global _loader
    if _loader is None:
        _loader = StoryLoader(config.data_path)
    return _loader


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


# ========== 엔드포인트 ==========


@router.get("/categories")
async def list_categories(lang: str | None = None):
    """스토리 카테고리 목록

    각 카테고리별 그룹 수와 에피소드 수를 반환
    """
    loader = get_loader()
    lang = lang or config.default_language

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
    loader = get_loader()
    lang = lang or config.default_language

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
    loader = get_loader()
    lang = lang or config.default_language

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
