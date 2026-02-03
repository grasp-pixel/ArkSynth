"""에피소드 관련 라우터"""

import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..config import config
from ...story.loader import StoryLoader
from ...voice.character_mapping import CharacterVoiceMapper

logger = logging.getLogger(__name__)
router = APIRouter()

# 전역 로더 (lazy init)
_loader: StoryLoader | None = None
_voice_mapper: CharacterVoiceMapper | None = None
_character_aliases: dict[str, str] | None = None


def _load_character_aliases() -> dict[str, str]:
    """캐릭터 별칭 매핑 로드

    NPC 이름 → 플레이어블 캐릭터 ID 매핑
    예: "모모카" → "char_4202_haruka"
    """
    global _character_aliases
    if _character_aliases is not None:
        return _character_aliases

    aliases_path = Path(config.data_path) / "character_aliases.json"
    if not aliases_path.exists():
        logger.info(f"캐릭터 별칭 파일 없음: {aliases_path}")
        _character_aliases = {}
        return _character_aliases

    try:
        with open(aliases_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            _character_aliases = data.get("aliases", {})
            logger.info(f"캐릭터 별칭 로드: {len(_character_aliases)}개")
    except Exception as e:
        logger.error(f"캐릭터 별칭 로드 실패: {e}")
        _character_aliases = {}

    return _character_aliases


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
    if not speaker_name:
        return None

    # 1. 별칭 매핑 확인 (NPC 이름 → 플레이어블 캐릭터 ID)
    aliases = _load_character_aliases()
    if speaker_name in aliases:
        alias_id = aliases[speaker_name]
        logger.debug(f"별칭 매핑: {speaker_name} → {alias_id}")
        return alias_id

    # 2. 이름 매칭 확인
    characters = loader.load_characters(lang)
    for char_id, char in characters.items():
        # char_로 시작하는 오퍼레이터만 (npc 제외)
        if char_id.startswith("char_") and not char_id.startswith("char_npc_"):
            if char.name_ko == speaker_name:
                return char_id
    return None


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

    # char_id 또는 speaker_name 기준으로 캐릭터 집계
    # key: char_id (있으면) 또는 "name:{speaker_name}" (없으면)
    # value: {names: [이름들], count, last_index}
    speaker_stats: dict[str, dict] = {}
    narration_count = 0  # 나레이션 대사 수 (char_id도 speaker_name도 없는 경우)

    for idx, dialogue in enumerate(episode.dialogues):
        speaker_name = dialogue.speaker_name or ""
        speaker_id = dialogue.speaker_id

        # 나레이션 판별: char_id도 없고 speaker_name도 없는 경우
        if not speaker_id and not speaker_name:
            narration_count += 1
            continue

        # char_id가 있으면 char_id로, 없으면 이름으로 키 생성
        key = speaker_id if speaker_id else f"name:{speaker_name}"

        if key not in speaker_stats:
            speaker_stats[key] = {
                "char_id": speaker_id,
                "names": [],
                "count": 0,
                "last_index": -1,
            }

        stats = speaker_stats[key]
        stats["count"] += 1
        stats["last_index"] = idx

        # 이름이 새로우면 추가 (순서 유지)
        if speaker_name and speaker_name not in stats["names"]:
            stats["names"].append(speaker_name)

    # 결과 정리 (대사 수 내림차순)
    characters = []
    for key, stats in speaker_stats.items():
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

        # 이름이 없으면 (이론상 발생하지 않지만) 스킵
        if not display_name:
            continue

        voice_char_id = None  # 실제 음성 파일이 있는 캐릭터 ID

        # 1. char_id로 음성 확인
        has_voice = voice_mapper.has_voice(char_id) if char_id else False
        if has_voice:
            voice_char_id = char_id

        # 2. 없으면 speaker_name으로 오퍼레이터 ID 찾아서 음성 확인
        #    (NPC로 등장하지만 나중에 오퍼레이터로 출시된 캐릭터)
        #    모든 이름에 대해 확인 (공개 전/후 이름 모두)
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
