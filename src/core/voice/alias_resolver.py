"""캐릭터 별칭 해결 모듈

NPC 이름이나 speaker_name으로 플레이어블 캐릭터 ID를 찾습니다.
예: "카지마치 주민" -> "char_4203_kichi"

이 모듈은 src.core.character 모듈과 통합되어 있습니다.
"""

import logging

from ..character import OfficialDataProvider, get_official_data_provider

logger = logging.getLogger(__name__)

# 싱글톤 OfficialDataProvider 사용
_provider: OfficialDataProvider | None = None


def _get_provider() -> OfficialDataProvider:
    """OfficialDataProvider 인스턴스 반환"""
    global _provider
    if _provider is None:
        _provider = get_official_data_provider()
    return _provider


def load_character_aliases(force_reload: bool = False) -> dict[str, str]:
    """캐릭터 별칭 매핑 로드 (호환성 유지용)

    Args:
        force_reload: True이면 캐시 무시하고 다시 로드

    Returns:
        dict[str, str]: {NPC이름: char_id} 매핑
    """
    provider = _get_provider()
    if force_reload:
        provider.invalidate_cache()
    return provider._load_user_aliases()


def load_character_table(force_reload: bool = False) -> dict[str, dict]:
    """캐릭터 테이블 로드 (호환성 유지용)

    Args:
        force_reload: True이면 캐시 무시하고 다시 로드

    Returns:
        dict[str, dict]: 캐릭터 테이블
    """
    provider = _get_provider()
    if force_reload:
        provider.invalidate_cache()
    return provider._load_character_table()


def invalidate_cache() -> None:
    """캐시 무효화"""
    provider = _get_provider()
    provider.invalidate_cache()
    logger.debug("별칭 해결 캐시 무효화")


def resolve_voice_char_id(
    speaker_name: str | None = None,
    char_id: str | None = None,
) -> str | None:
    """speaker_name 또는 char_id로 음성이 있는 캐릭터 ID 찾기

    우선순위:
    1. 사용자 별칭 매핑 확인 (character_aliases.json)
    2. 공식 이름 매칭 확인 (character_table.json)

    Args:
        speaker_name: 화자 이름 (예: "카지마치 주민", "모모카")
        char_id: 캐릭터 ID (NPC ID 포함, 예: "char_npc_xxx")

    Returns:
        str | None: 음성이 있는 플레이어블 캐릭터 ID (예: "char_4203_kichi")
    """
    if not speaker_name:
        return None

    provider = _get_provider()

    # OfficialDataProvider.get_char_id_by_name()은 사용자 별칭과 공식 이름을 모두 확인
    result = provider.get_char_id_by_name(speaker_name)

    if result:
        # 플레이어블 캐릭터만 반환 (char_로 시작하고 npc가 아닌 것)
        if result.startswith("char_") and "_npc_" not in result:
            logger.debug(f"음성 캐릭터 매핑: {speaker_name} → {result}")
            return result

    return None
