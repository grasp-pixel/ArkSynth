"""에피소드 관련 라우터"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..config import config
from ...story.loader import StoryLoader
from ...voice.character_mapping import CharacterVoiceMapper

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
    """
    if not speaker_name:
        return None

    characters = loader.load_characters(lang)
    for char_id, char in characters.items():
        # char_로 시작하는 오퍼레이터만 (npc 제외)
        if char_id.startswith("char_") and not char_id.startswith("char_npc_"):
            if char.name_ko == speaker_name:
                return char_id
    return None


@router.get("/{episode_id}/characters")
async def get_episode_characters(episode_id: str, lang: str | None = None):
    """에피소드에 등장하는 캐릭터(화자) 목록

    speaker_name 기반으로 집계하여 실제 에피소드에서 표시되는 이름 사용.
    같은 char_id라도 다른 speaker_name이면 별도 항목으로 표시.
    """
    loader = get_loader()
    voice_mapper = get_voice_mapper()
    lang = lang or config.game_language

    episode = loader.load_episode(episode_id, lang=lang)

    if episode is None:
        raise HTTPException(status_code=404, detail=f"Episode not found: {episode_id}")

    # speaker_name 기준으로 캐릭터 집계
    # key: speaker_name, value: {char_id, count}
    speaker_stats: dict[str, dict] = {}

    for dialogue in episode.dialogues:
        speaker_name = dialogue.speaker_name or ""
        speaker_id = dialogue.speaker_id

        if speaker_name not in speaker_stats:
            speaker_stats[speaker_name] = {
                "char_id": speaker_id,
                "count": 0,
            }
        speaker_stats[speaker_name]["count"] += 1

    # 결과 정리 (대사 수 내림차순)
    characters = []
    for speaker_name, stats in speaker_stats.items():
        char_id = stats["char_id"]
        voice_char_id = None  # 실제 음성 파일이 있는 캐릭터 ID

        # 1. char_id로 음성 확인
        has_voice = voice_mapper.has_voice(char_id) if char_id else False
        if has_voice:
            voice_char_id = char_id

        # 2. 없으면 speaker_name으로 오퍼레이터 ID 찾아서 음성 확인
        #    (NPC로 등장하지만 나중에 오퍼레이터로 출시된 캐릭터)
        if not has_voice and speaker_name:
            operator_id = _find_operator_id_by_name(loader, speaker_name, lang)
            if operator_id and voice_mapper.has_voice(operator_id):
                has_voice = True
                voice_char_id = operator_id  # 이름 매칭된 오퍼레이터 ID 저장

        characters.append(
            EpisodeCharacterInfo(
                char_id=char_id,
                name=speaker_name or "나레이터",
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
    }
