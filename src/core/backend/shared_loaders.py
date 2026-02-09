"""공유 로더 인스턴스 관리

stories.py, episodes.py 등에서 동일한 로더 인스턴스를 사용하기 위한 중앙 관리 모듈.
"""

from ..story.loader import StoryLoader
from ..voice.character_mapping import CharacterVoiceMapper
from ..character.official_data import get_official_data_provider
from .config import config

# 전역 로더 인스턴스
_story_loader: StoryLoader | None = None
_voice_mapper: CharacterVoiceMapper | None = None


def get_story_loader() -> StoryLoader:
    """스토리 로더 인스턴스 반환 (싱글톤)"""
    global _story_loader
    if _story_loader is None:
        _story_loader = StoryLoader(config.data_path)
    return _story_loader


def get_voice_mapper() -> CharacterVoiceMapper:
    """음성 매퍼 인스턴스 반환 (싱글톤)"""
    global _voice_mapper
    if _voice_mapper is None:
        _voice_mapper = CharacterVoiceMapper(
            extracted_path=config.extracted_path,
            gamedata_path=config.gamedata_path,
            default_lang=config.voice_language,
        )
    return _voice_mapper


def reset_story_loader() -> None:
    """스토리 로더 인스턴스 리셋 (캐시 무효화)"""
    global _story_loader
    _story_loader = None


def reset_voice_mapper() -> None:
    """음성 매퍼 인스턴스 리셋"""
    global _voice_mapper
    _voice_mapper = None


def reset_all() -> None:
    """모든 로더 리셋"""
    reset_story_loader()
    reset_voice_mapper()
    # 렌더 캐시도 리셋
    from .routes.render import reset_render_cache
    reset_render_cache()


def find_operator_id_by_name(
    loader: StoryLoader, speaker_name: str, lang: str
) -> str | None:
    """speaker_name으로 오퍼레이터 ID 찾기

    1. OfficialDataProvider에서 별칭(본명 등) 포함 조회
    2. 캐릭터 테이블에서 이름이 일치하는 플레이어블 캐릭터 검색
    정확히 일치 우선, 부분 일치(이름이 검색어로 시작)도 지원.
    예: "조르디" → char_4042_lumen (별칭)
        "하이디" → char_4045_heidi
        "비나" → char_1019_siege2 (비나 빅토리아)
    """
    if not speaker_name:
        return None

    # 1. OfficialDataProvider에서 별칭 포함 조회 (본명, 닉네임 등)
    provider = get_official_data_provider()
    char_id = provider.get_char_id_by_name(speaker_name)
    if char_id:
        return char_id

    # 2. 캐릭터 테이블에서 부분 일치 검색
    characters = loader.load_characters(lang)
    prefix_match: str | None = None  # 부분 일치 후보

    for char_id, char in characters.items():
        # char_로 시작하는 오퍼레이터만 (npc 제외)
        if char_id.startswith("char_") and not char_id.startswith("char_npc_"):
            name = char.name_ko or ""
            # 부분 일치: 이름이 검색어로 시작 (예: "비나 빅토리아".startswith("비나"))
            if name.startswith(speaker_name + " ") and not prefix_match:
                prefix_match = char_id

    return prefix_match
