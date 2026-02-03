"""에피소드 관련 라우터"""

import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..config import config
from ...story.loader import StoryLoader
from ...voice.character_mapping import CharacterVoiceMapper
from ...voice.alias_resolver import load_character_aliases, resolve_voice_char_id

logger = logging.getLogger(__name__)
router = APIRouter()

# 전역 로더 (lazy init)
_loader: StoryLoader | None = None
_voice_mapper: CharacterVoiceMapper | None = None


def get_loader() -> StoryLoader:
    global _loader
    if _loader is None:
        _loader = StoryLoader(config.data_path)
    return _loader


def get_voice_mapper() -> CharacterVoiceMapper:
    global _voice_mapper
    if _voice_mapper is None:
        _voice_mapper = CharacterVoiceMapper(
            extracted_path=config.extracted_path,
        )
    return _voice_mapper


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
    loader = get_loader()
    lang = lang or config.game_language

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
    loader = get_loader()
    lang = lang or config.game_language

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
    loader = get_loader()
    lang = lang or config.game_language

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


def _find_operator_id_by_name(
    loader: StoryLoader, speaker_name: str, lang: str
) -> str | None:
    """speaker_name으로 오퍼레이터 ID 찾기

    NPC ID(char_npc_XXX)로는 음성이 없지만, 같은 이름의 오퍼레이터가
    나중에 출시된 경우를 처리. 예: "하이디" → char_4045_heidi

    1. 별칭 매핑 확인 (모모카 → char_4202_haruka)
    2. 이름 매칭 확인 (하이디 → char_4045_heidi)
    """
    # 공통 모듈의 resolve_voice_char_id 사용
    return resolve_voice_char_id(speaker_name=speaker_name)


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
    loader = get_loader()
    voice_mapper = get_voice_mapper()
    lang = lang or config.game_language

    episode = loader.load_episode(episode_id, lang=lang)

    if episode is None:
        raise HTTPException(status_code=404, detail=f"Episode not found: {episode_id}")

    # 캐릭터 집계 로직:
    # 1. speaker_id의 캐릭터 이름과 speaker_name이 일치하면 → speaker_id 기준 (같은 캐릭터)
    # 2. speaker_id의 캐릭터 이름과 speaker_name이 다르면 → speaker_name 기준 (다른 캐릭터가 말함)
    # 이렇게 해야 "???" → "미후네" 케이스와 "스카디 화면에 켈시가 말함" 케이스 모두 처리 가능
    speaker_stats: dict[str, dict] = {}
    narration_count = 0

    # CharacterNameMapper로 speaker_name → char_id 매핑
    name_mapper = loader.get_name_mapper()
    characters_table = loader.load_characters(lang)

    def get_char_name(char_id: str) -> str | None:
        """char_id로 캐릭터 이름 조회 (정규화 포함)"""
        if not char_id:
            return None
        # 정규화된 ID로 조회
        normalized = loader._normalize_char_id(char_id)
        char = characters_table.get(normalized)
        return char.name_ko if char else None

    for idx, dialogue in enumerate(episode.dialogues):
        speaker_name = dialogue.speaker_name or ""
        speaker_id = dialogue.speaker_id

        # 나레이션 판별
        if not speaker_id and not speaker_name:
            narration_count += 1
            continue

        # 키 결정: speaker_id의 캐릭터 이름과 speaker_name 비교
        char_name_from_id = get_char_name(speaker_id) if speaker_id else None

        if speaker_id and char_name_from_id:
            # speaker_id가 있고 캐릭터 이름을 찾았을 때
            if char_name_from_id == speaker_name or _is_mystery_name(speaker_name):
                # 같은 캐릭터 또는 "???" 같은 미스터리 이름 → speaker_id 기준
                key = speaker_id
            else:
                # 다른 캐릭터가 말함 (예: 스카디 화면에 켈시가 말함) → speaker_name 기준
                key = f"name:{speaker_name}"
        elif speaker_id:
            # speaker_id는 있지만 캐릭터 테이블에 없음 (NPC 등)
            key = speaker_id
        else:
            # speaker_id 없음 → speaker_name 기준
            key = f"name:{speaker_name}"

        if key not in speaker_stats:
            # char_id 결정
            if key.startswith("name:"):
                char_id = name_mapper.get_char_id(speaker_name)
            else:
                char_id = loader._normalize_char_id(key)

            speaker_stats[key] = {
                "char_id": char_id,
                "names": [],
                "count": 0,
                "last_index": -1,
            }

        stats = speaker_stats[key]
        stats["count"] += 1
        stats["last_index"] = idx

        # 이름 수집 (순서 유지)
        if speaker_name and speaker_name not in stats["names"]:
            stats["names"].append(speaker_name)

    # 같은 char_id끼리 병합 (정규화된 char_id 기준)
    merged_stats: dict[str, dict] = {}
    for key, stats in speaker_stats.items():
        char_id = stats["char_id"]
        # char_id가 없으면 키를 그대로 사용
        merge_key = char_id or key

        if merge_key not in merged_stats:
            merged_stats[merge_key] = {
                "char_id": char_id,
                "names": [],
                "count": 0,
            }

        merged = merged_stats[merge_key]
        merged["count"] += stats["count"]
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
                    operator_id = _find_operator_id_by_name(loader, name, lang)
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
