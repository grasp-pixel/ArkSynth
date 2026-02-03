"""캐릭터 별칭 해결 모듈

NPC 이름이나 speaker_name으로 플레이어블 캐릭터 ID를 찾습니다.
예: "카지마치 주민" -> "char_4203_kichi"
"""

import json
import logging
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

# 모듈 레벨 캐시
_character_aliases: dict[str, str] | None = None
_character_table: dict[str, dict] | None = None


def _get_data_path() -> Path:
    """데이터 경로 반환"""
    from ..backend.config import config
    return Path(config.data_path)


def _get_gamedata_path() -> Path:
    """게임 데이터 경로 반환"""
    from ..backend.config import config
    return Path(config.data_path) / "gamedata" / "kr" / "gamedata"


def load_character_aliases(force_reload: bool = False) -> dict[str, str]:
    """캐릭터 별칭 매핑 로드

    Args:
        force_reload: True이면 캐시 무시하고 다시 로드

    Returns:
        dict[str, str]: {NPC이름: char_id} 매핑
    """
    global _character_aliases
    if _character_aliases is not None and not force_reload:
        return _character_aliases

    aliases_path = _get_data_path() / "character_aliases.json"
    if not aliases_path.exists():
        logger.debug(f"캐릭터 별칭 파일 없음: {aliases_path}")
        _character_aliases = {}
        return _character_aliases

    try:
        with open(aliases_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            _character_aliases = data.get("aliases", {})
            logger.debug(f"캐릭터 별칭 로드: {len(_character_aliases)}개")
    except Exception as e:
        logger.error(f"캐릭터 별칭 로드 실패: {e}")
        _character_aliases = {}

    return _character_aliases


def load_character_table(force_reload: bool = False) -> dict[str, dict]:
    """캐릭터 테이블 로드 (이름 -> char_id 매핑용)

    Args:
        force_reload: True이면 캐시 무시하고 다시 로드

    Returns:
        dict[str, dict]: 캐릭터 테이블
    """
    global _character_table
    if _character_table is not None and not force_reload:
        return _character_table

    table_path = _get_gamedata_path() / "excel" / "character_table.json"
    if not table_path.exists():
        logger.debug(f"캐릭터 테이블 파일 없음: {table_path}")
        _character_table = {}
        return _character_table

    try:
        with open(table_path, "r", encoding="utf-8") as f:
            _character_table = json.load(f)
            logger.debug(f"캐릭터 테이블 로드: {len(_character_table)}개")
    except Exception as e:
        logger.error(f"캐릭터 테이블 로드 실패: {e}")
        _character_table = {}

    return _character_table


def invalidate_cache() -> None:
    """캐시 무효화"""
    global _character_aliases, _character_table
    _character_aliases = None
    _character_table = None
    logger.debug("별칭 해결 캐시 무효화")


def resolve_voice_char_id(
    speaker_name: str | None = None,
    char_id: str | None = None,
) -> str | None:
    """speaker_name 또는 char_id로 음성이 있는 캐릭터 ID 찾기

    우선순위:
    1. 별칭 매핑 확인 (speaker_name → char_id)
    2. 이름 매칭 확인 (speaker_name → character_table에서 같은 이름의 오퍼레이터)

    Args:
        speaker_name: 화자 이름 (예: "카지마치 주민", "모모카")
        char_id: 캐릭터 ID (NPC ID 포함, 예: "char_npc_xxx")

    Returns:
        str | None: 음성이 있는 플레이어블 캐릭터 ID (예: "char_4203_kichi")
    """
    if not speaker_name:
        return None

    # 1. 별칭 매핑 확인 (NPC 이름 → 플레이어블 캐릭터 ID)
    aliases = load_character_aliases()
    if speaker_name in aliases:
        alias_id = aliases[speaker_name]
        logger.debug(f"별칭 매핑: {speaker_name} → {alias_id}")
        return alias_id

    # 2. 이름 매칭 확인 (character_table에서 같은 이름의 오퍼레이터)
    char_table = load_character_table()
    for cid, char_data in char_table.items():
        # char_로 시작하는 오퍼레이터만 (npc 제외)
        if cid.startswith("char_") and not cid.startswith("char_npc_"):
            if char_data.get("name") == speaker_name:
                logger.debug(f"이름 매칭: {speaker_name} → {cid}")
                return cid

    return None
