"""에피소드 관련 라우터"""

import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..config import config
from ..shared_loaders import get_story_loader, get_voice_mapper, find_operator_id_by_name
from ...voice.alias_resolver import resolve_voice_char_id

logger = logging.getLogger(__name__)
router = APIRouter()


class EpisodeSummary(BaseModel):
    """에피소드 요약 정보"""

    id: str
    code: str  # "0-1", "1-7"
    name: str  # "어둠 속에서"
    tag: str  # "작전 전", "작전 후"
    chapter: str  # "서장", "제1장"
    display_name: str  # "0-1 어둠 속에서"


class DialogueInfo(BaseModel):
    """대사 정보"""

    id: str
    speaker_id: str | None
    speaker_name: str
    text: str
    line_number: int
    dialogue_type: str = "dialogue"  # "dialogue" | "narration" | "subtitle"


class EpisodeDetail(BaseModel):
    """에피소드 상세 정보"""

    id: str
    title: str
    dialogues: list[DialogueInfo]
    characters: list[str]


@router.get("/main")
async def list_main_episodes(lang: str | None = None):
    """메인 스토리 에피소드 목록

    Args:
        lang: 언어 코드 (기본값: ko_KR)
    """
    loader = get_story_loader()
    lang = lang or config.display_language

    episodes = loader.list_main_episodes(lang=lang)

    # 챕터별로 그룹화
    chapters: dict[str, list] = {}
    for ep in episodes:
        chapter = ep["chapter"]
        if chapter not in chapters:
            chapters[chapter] = []
        chapters[chapter].append(
            EpisodeSummary(
                id=ep["id"],
                code=ep["code"],
                name=ep["name"],
                tag=ep["tag"],
                chapter=ep["chapter"],
                display_name=ep["display_name"],
            )
        )

    return {
        "total": len(episodes),
        "language": lang,
        "chapters": chapters,
        "episodes": [
            EpisodeSummary(
                id=ep["id"],
                code=ep["code"],
                name=ep["name"],
                tag=ep["tag"],
                chapter=ep["chapter"],
                display_name=ep["display_name"],
            )
            for ep in episodes
        ],
    }


@router.get("/{episode_id}")
async def get_episode(episode_id: str, lang: str | None = None):
    """에피소드 상세 정보 조회"""
    loader = get_story_loader()
    lang = lang or config.display_language

    episode = loader.load_episode(episode_id, lang=lang)

    if episode is None:
        raise HTTPException(status_code=404, detail=f"Episode not found: {episode_id}")

    return EpisodeDetail(
        id=episode.id,
        title=episode.title,
        dialogues=[
            DialogueInfo(
                id=d.id,
                speaker_id=d.speaker_id,
                speaker_name=d.speaker_name,
                text=d.text,
                line_number=d.line_number,
                dialogue_type=d.dialogue_type.value,
            )
            for d in episode.dialogues
        ],
        characters=list(episode.characters),
    )


@router.get("/{episode_id}/dialogues")
async def get_episode_dialogues(
    episode_id: str,
    lang: str | None = None,
    offset: int = 0,
    limit: int = 50,
):
    """에피소드 대사 목록 (페이지네이션)"""
    loader = get_story_loader()
    lang = lang or config.display_language

    episode = loader.load_episode(episode_id, lang=lang)

    if episode is None:
        raise HTTPException(status_code=404, detail=f"Episode not found: {episode_id}")

    dialogues = episode.dialogues[offset : offset + limit]

    return {
        "total": len(episode.dialogues),
        "offset": offset,
        "limit": limit,
        "dialogues": [
            DialogueInfo(
                id=d.id,
                speaker_id=d.speaker_id,
                speaker_name=d.speaker_name,
                text=d.text,
                line_number=d.line_number,
                dialogue_type=d.dialogue_type.value,
            )
            for d in dialogues
        ],
    }


class EpisodeCharacterInfo(BaseModel):
    """에피소드 내 캐릭터(화자) 정보"""

    char_id: str | None  # None이면 나레이터
    name: str  # speaker_name (화자 표시 이름)
    dialogue_count: int
    has_voice: bool
    voice_char_id: str | None = None  # 실제 음성 파일이 있는 캐릭터 ID (이름 매칭 시)


def _is_mystery_name(name: str) -> bool:
    """이름이 '???' 같은 미스터리 이름인지 확인"""
    if not name:
        return True
    # '?'로만 구성되거나, '?'로 끝나는 경우
    stripped = name.strip()
    return stripped.endswith("?") or all(c == "?" for c in stripped)


@router.get("/{episode_id}/characters")
async def get_episode_characters(episode_id: str, lang: str | None = None):
    """에피소드에 등장하는 캐릭터(화자) 목록

    char_id 기반으로 집계하여 같은 캐릭터의 대사를 합산.
    이름이 변하는 경우 (예: "???" → "미오") 최종 공개된 이름을 표시.
    char_id가 없는 경우 speaker_name으로 구분.
    나레이션(char_id도 speaker_name도 없는 대사)은 별도로 집계.
    """
    loader = get_story_loader()
    voice_mapper = get_voice_mapper()
    lang = lang or config.display_language

    episode = loader.load_episode(episode_id, lang=lang)

    if episode is None:
        raise HTTPException(status_code=404, detail=f"Episode not found: {episode_id}")

    # 화자 집계 (공통 로직 사용)
    speaker_stats, narration_count = loader.collect_episode_speakers(episode, lang)

    # 같은 char_id끼리 병합 (정규화된 char_id 기준)
    merged_stats: dict[str, dict] = {}
    for key, stats in speaker_stats.items():
        char_id = stats["char_id"]
        merge_key = char_id or key

        if merge_key not in merged_stats:
            merged_stats[merge_key] = {
                "char_id": char_id,
                "names": [],
                "count": 0,
            }

        merged = merged_stats[merge_key]
        merged["count"] += stats["count"]
        if char_id and not merged["char_id"]:
            merged["char_id"] = char_id
        for name in stats["names"]:
            if name and name not in merged["names"]:
                merged["names"].append(name)

    # 결과 정리 (대사 수 내림차순)
    characters = []
    for key, stats in merged_stats.items():
        char_id = stats["char_id"]
        names = stats["names"]

        # 표시할 이름 결정: 미스터리 이름이 아닌 마지막 이름 선호
        display_name = ""
        for name in reversed(names):
            if not _is_mystery_name(name):
                display_name = name
                break
        # 모두 미스터리 이름이면 마지막 이름 사용
        if not display_name and names:
            display_name = names[-1]

        # 이름이 없으면 스킵
        if not display_name:
            continue

        voice_char_id = None  # 실제 음성 파일이 있는 캐릭터 ID

        # 1. char_id로 음성 확인
        has_voice = voice_mapper.has_voice(char_id) if char_id else False
        if has_voice:
            voice_char_id = char_id

        # 2. 없으면 speaker_name으로 오퍼레이터 ID 찾아서 음성 확인
        #    (NPC로 등장하지만 나중에 오퍼레이터로 출시된 캐릭터)
        if not has_voice:
            for name in names:
                if name:
                    operator_id = find_operator_id_by_name(loader, name, lang)
                    if operator_id and voice_mapper.has_voice(operator_id):
                        has_voice = True
                        voice_char_id = operator_id
                        break

        characters.append(
            EpisodeCharacterInfo(
                char_id=char_id,
                name=display_name,
                dialogue_count=stats["count"],
                has_voice=has_voice,
                voice_char_id=voice_char_id,
            )
        )

    # 대사 수 내림차순 정렬
    characters.sort(key=lambda c: c.dialogue_count, reverse=True)

    return {
        "episode_id": episode_id,
        "total": len(characters),
        "characters": characters,
        "narration_count": narration_count,  # 나레이션 대사 수
    }
