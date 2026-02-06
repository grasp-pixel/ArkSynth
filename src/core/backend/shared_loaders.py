"""공유 로더 인스턴스 관리

stories.py, episodes.py 등에서 동일한 로더 인스턴스를 사용하기 위한 중앙 관리 모듈.
"""

from ..story.loader import StoryLoader
from ..voice.character_mapping import CharacterVoiceMapper
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
            gamedata_path=config.gamedata_yostar_path,
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
