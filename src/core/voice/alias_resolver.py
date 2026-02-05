"""스프라이트 ID → 음성 캐릭터 ID 매핑 모듈

스프라이트 ID로 음성이 있는 플레이어블 캐릭터 ID를 찾습니다.
- 플레이어블 캐릭터(char_XXX): 그대로 반환
- NPC(avg_npc_XXX): voice_mapping.json에서 매핑 확인

v2 스키마:
- voice_mapping: {sprite_id: {"voice_char_id": "...", "source": "manual|auto"}}
- 특수값 지원: __auto_female__, __auto_male__
"""

import json
import logging
from pathlib import Path
from typing import TypedDict, Literal

from ..character import CharacterIdNormalizer

logger = logging.getLogger(__name__)

# 특수값 (프론트엔드와 동기화)
AUTO_VOICE_FEMALE = "__auto_female__"
AUTO_VOICE_MALE = "__auto_male__"

# v2 타입 정의
MappingSource = Literal["manual", "auto"]

class VoiceMappingEntry(TypedDict, total=False):
    voice_char_id: str
    source: MappingSource

# 음성 매핑 캐시 (v2: dict[sprite_id, VoiceMappingEntry])
_voice_mapping: dict[str, VoiceMappingEntry] | None = None
_voice_mapping_path: Path | None = None
_schema_version: int = 1  # 로드된 스키마 버전


def _get_voice_mapping_path() -> Path:
    """voice_mapping.json 경로 반환"""
    global _voice_mapping_path
    if _voice_mapping_path is None:
        # data/voice_mapping.json
        _voice_mapping_path = Path(__file__).parent.parent.parent.parent / "data" / "voice_mapping.json"
    return _voice_mapping_path


def _migrate_v1_to_v2(data: dict) -> dict:
    """v1 스키마를 v2로 마이그레이션

    v1: {"voice_mapping": {"sprite_id": "voice_char_id"}}
    v2: {"_version": 2, "voice_mapping": {"sprite_id": {"voice_char_id": "...", "source": "manual"}}}
    """
    if data.get("_version", 1) >= 2:
        return data  # 이미 v2

    old_mapping = data.get("voice_mapping", {})
    new_mapping = {}

    for sprite_id, voice_char_id in old_mapping.items():
        if isinstance(voice_char_id, str):
            # v1: 문자열 → v2: 객체로 변환
            new_mapping[sprite_id] = {
                "voice_char_id": voice_char_id,
                "source": "manual"  # 기존 데이터는 수동으로 간주
            }
        elif isinstance(voice_char_id, dict):
            # 이미 v2 형식
            new_mapping[sprite_id] = voice_char_id

    return {
        "_version": 2,
        "_comment": data.get("_comment", "스프라이트 ID → 음성 캐릭터 ID 매핑"),
        "voice_mapping": new_mapping
    }


def _load_voice_mapping() -> dict[str, VoiceMappingEntry]:
    """음성 매핑 로드 (v2 형식으로 반환)"""
    global _voice_mapping, _schema_version
    if _voice_mapping is not None:
        return _voice_mapping

    mapping_path = _get_voice_mapping_path()
    if not mapping_path.exists():
        _voice_mapping = {}
        _schema_version = 2
        return _voice_mapping

    try:
        with open(mapping_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # v1 → v2 마이그레이션 (메모리에서만)
        original_version = data.get("_version", 1)
        data = _migrate_v1_to_v2(data)
        _schema_version = 2

        # 마이그레이션이 필요했다면 파일에도 저장
        if original_version < 2:
            logger.info("voice_mapping.json을 v2 스키마로 마이그레이션합니다")
            try:
                with open(mapping_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                logger.info("v2 마이그레이션 완료")
            except Exception as e:
                logger.warning(f"v2 마이그레이션 저장 실패 (계속 진행): {e}")

        _voice_mapping = data.get("voice_mapping", {})
    except Exception as e:
        logger.warning(f"voice_mapping.json 로드 실패: {e}")
        _voice_mapping = {}
        _schema_version = 2

    return _voice_mapping


def invalidate_cache() -> None:
    """캐시 무효화"""
    global _voice_mapping, _schema_version
    _voice_mapping = None
    _schema_version = 1
    logger.debug("음성 매핑 캐시 무효화")


def resolve_voice_char_id(sprite_id: str | None) -> str | None:
    """스프라이트 ID로 음성 캐릭터 ID 찾기

    Args:
        sprite_id: 정규화된 스프라이트 ID (char_002_amiya, avg_npc_109 등)

    Returns:
        str | None: 음성이 있는 플레이어블 캐릭터 ID, 특수값, 또는 None

    우선순위:
    1. 플레이어블 캐릭터(char_로 시작, _npc_ 미포함): 그대로 반환
    2. NPC: voice_mapping.json에서 매핑 확인 (특수값 포함)
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

    # NPC면 voice_mapping에서 매핑 확인 (v2 형식)
    mapping = _load_voice_mapping()
    entry = mapping.get(normalized_id)

    if entry:
        voice_char_id = entry.get("voice_char_id") if isinstance(entry, dict) else entry
        if voice_char_id:
            logger.debug(f"음성 매핑: {normalized_id} → {voice_char_id}")
            return voice_char_id

    return None


def save_voice_mapping(
    sprite_id: str,
    voice_char_id: str,
    source: MappingSource = "manual"
) -> bool:
    """음성 매핑 저장 (v2 형식)

    Args:
        sprite_id: 스프라이트 ID (NPC ID 또는 name:XXX)
        voice_char_id: 매핑할 음성 캐릭터 ID 또는 특수값 (__auto_female__, __auto_male__)
        source: 매핑 출처 (manual, auto)

    Returns:
        bool: 저장 성공 여부
    """
    mapping_path = _get_voice_mapping_path()

    # 기존 데이터 로드
    if mapping_path.exists():
        try:
            with open(mapping_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # v1이면 v2로 마이그레이션
            data = _migrate_v1_to_v2(data)
        except Exception:
            data = {"_version": 2, "voice_mapping": {}}
    else:
        data = {"_version": 2, "voice_mapping": {}}

    # voice_mapping 섹션 업데이트
    if "voice_mapping" not in data:
        data["voice_mapping"] = {}

    # ID 정규화 (sprite_id만, voice_char_id는 특수값일 수 있음)
    normalizer = CharacterIdNormalizer()

    # name: 접두사는 정규화하지 않음
    if sprite_id.startswith("name:"):
        normalized_sprite = sprite_id
    else:
        normalized_sprite = normalizer.normalize(sprite_id)

    # 특수값은 정규화하지 않음
    is_special_value = voice_char_id in (AUTO_VOICE_FEMALE, AUTO_VOICE_MALE)
    if is_special_value:
        normalized_voice = voice_char_id
    else:
        normalized_voice = normalizer.normalize(voice_char_id)

    # v2 형식으로 저장
    data["voice_mapping"][normalized_sprite] = {
        "voice_char_id": normalized_voice,
        "source": source
    }

    # 저장
    try:
        mapping_path.parent.mkdir(parents=True, exist_ok=True)
        with open(mapping_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        # 캐시 무효화
        invalidate_cache()
        logger.info(f"음성 매핑 저장: {normalized_sprite} → {normalized_voice} (source={source})")
        return True
    except Exception as e:
        logger.error(f"음성 매핑 저장 실패: {e}")
        return False


def delete_voice_mapping(sprite_id: str) -> bool:
    """음성 매핑 삭제

    Args:
        sprite_id: 삭제할 스프라이트 ID (name:XXX 형식도 지원)

    Returns:
        bool: 삭제 성공 여부
    """
    mapping_path = _get_voice_mapping_path()

    if not mapping_path.exists():
        return False

    try:
        with open(mapping_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # v1이면 v2로 마이그레이션
        data = _migrate_v1_to_v2(data)
    except Exception:
        return False

    voice_mapping = data.get("voice_mapping", {})

    # ID 정규화 (name: 접두사는 정규화하지 않음)
    if sprite_id.startswith("name:"):
        normalized_id = sprite_id
    else:
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


def get_all_voice_mappings() -> dict[str, VoiceMappingEntry]:
    """모든 음성 매핑 반환 (v2 형식: sprite_id → {voice_char_id, source})"""
    return _load_voice_mapping().copy()


def get_all_voice_mappings_flat() -> dict[str, str]:
    """모든 음성 매핑 반환 (플랫 형식: sprite_id → voice_char_id)

    프론트엔드 호환용. v2 형식에서 voice_char_id만 추출.
    """
    mapping = _load_voice_mapping()
    result = {}
    for sprite_id, entry in mapping.items():
        if isinstance(entry, dict):
            voice_char_id = entry.get("voice_char_id")
            if voice_char_id:
                result[sprite_id] = voice_char_id
        elif isinstance(entry, str):
            # v1 형식 호환
            result[sprite_id] = entry
    return result
