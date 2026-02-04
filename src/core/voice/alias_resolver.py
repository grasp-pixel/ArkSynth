"""스프라이트 ID → 음성 캐릭터 ID 매핑 모듈

스프라이트 ID로 음성이 있는 플레이어블 캐릭터 ID를 찾습니다.
- 플레이어블 캐릭터(char_XXX): 그대로 반환
- NPC(avg_npc_XXX): voice_mapping.json에서 매핑 확인
"""

import json
import logging
from pathlib import Path

from ..character import CharacterIdNormalizer

logger = logging.getLogger(__name__)

# 음성 매핑 캐시
_voice_mapping: dict[str, str] | None = None
_voice_mapping_path: Path | None = None


def _get_voice_mapping_path() -> Path:
    """voice_mapping.json 경로 반환"""
    global _voice_mapping_path
    if _voice_mapping_path is None:
        # data/voice_mapping.json
        _voice_mapping_path = Path(__file__).parent.parent.parent.parent / "data" / "voice_mapping.json"
    return _voice_mapping_path


def _load_voice_mapping() -> dict[str, str]:
    """음성 매핑 로드"""
    global _voice_mapping
    if _voice_mapping is not None:
        return _voice_mapping

    mapping_path = _get_voice_mapping_path()
    if not mapping_path.exists():
        _voice_mapping = {}
        return _voice_mapping

    try:
        with open(mapping_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        _voice_mapping = data.get("voice_mapping", {})
    except Exception as e:
        logger.warning(f"voice_mapping.json 로드 실패: {e}")
        _voice_mapping = {}

    return _voice_mapping


def invalidate_cache() -> None:
    """캐시 무효화"""
    global _voice_mapping
    _voice_mapping = None
    logger.debug("음성 매핑 캐시 무효화")


def resolve_voice_char_id(sprite_id: str | None) -> str | None:
    """스프라이트 ID로 음성 캐릭터 ID 찾기

    Args:
        sprite_id: 정규화된 스프라이트 ID (char_002_amiya, avg_npc_109 등)

    Returns:
        str | None: 음성이 있는 플레이어블 캐릭터 ID 또는 None

    우선순위:
    1. 플레이어블 캐릭터(char_로 시작, _npc_ 미포함): 그대로 반환
    2. NPC: voice_mapping.json에서 매핑 확인
    3. 매핑 없으면 None (UI에서 선택 필요)
    """
    if not sprite_id:
        return None

    # ID 정규화
    normalizer = CharacterIdNormalizer()
    normalized_id = normalizer.normalize(sprite_id)

    # 플레이어블 캐릭터인지 확인
    if normalizer.is_playable(normalized_id):
        return normalized_id

    # NPC면 voice_mapping에서 매핑 확인
    mapping = _load_voice_mapping()
    mapped_id = mapping.get(normalized_id)

    if mapped_id:
        logger.debug(f"음성 매핑: {normalized_id} → {mapped_id}")
        return mapped_id

    return None


def save_voice_mapping(sprite_id: str, voice_char_id: str) -> bool:
    """음성 매핑 저장

    Args:
        sprite_id: 스프라이트 ID (NPC ID)
        voice_char_id: 매핑할 음성 캐릭터 ID

    Returns:
        bool: 저장 성공 여부
    """
    mapping_path = _get_voice_mapping_path()

    # 기존 데이터 로드
    if mapping_path.exists():
        try:
            with open(mapping_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
    else:
        data = {}

    # voice_mapping 섹션 업데이트
    if "voice_mapping" not in data:
        data["voice_mapping"] = {}

    # ID 정규화
    normalizer = CharacterIdNormalizer()
    normalized_sprite = normalizer.normalize(sprite_id)
    normalized_voice = normalizer.normalize(voice_char_id)

    data["voice_mapping"][normalized_sprite] = normalized_voice

    # 저장
    try:
        mapping_path.parent.mkdir(parents=True, exist_ok=True)
        with open(mapping_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        # 캐시 무효화
        invalidate_cache()
        logger.info(f"음성 매핑 저장: {normalized_sprite} → {normalized_voice}")
        return True
    except Exception as e:
        logger.error(f"음성 매핑 저장 실패: {e}")
        return False


def delete_voice_mapping(sprite_id: str) -> bool:
    """음성 매핑 삭제

    Args:
        sprite_id: 삭제할 스프라이트 ID

    Returns:
        bool: 삭제 성공 여부
    """
    mapping_path = _get_voice_mapping_path()

    if not mapping_path.exists():
        return False

    try:
        with open(mapping_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return False

    voice_mapping = data.get("voice_mapping", {})

    # ID 정규화
    normalizer = CharacterIdNormalizer()
    normalized_id = normalizer.normalize(sprite_id)

    if normalized_id not in voice_mapping:
        return False

    del voice_mapping[normalized_id]
    data["voice_mapping"] = voice_mapping

    try:
        with open(mapping_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        invalidate_cache()
        logger.info(f"음성 매핑 삭제: {normalized_id}")
        return True
    except Exception as e:
        logger.error(f"음성 매핑 삭제 실패: {e}")
        return False


def get_all_voice_mappings() -> dict[str, str]:
    """모든 음성 매핑 반환"""
    return _load_voice_mapping().copy()
