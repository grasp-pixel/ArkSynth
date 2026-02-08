"""캐릭터 ID 정규화 모듈

프로젝트 전체에서 단일 ID 정규화 기준을 사용합니다.
기존 character_name_mapper.py, loader.py, parser.py의 정규화 로직을 통합했습니다.
"""

import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# 스프라이트 번호 → character_table ID 매핑 캐시
_number_to_table_id: dict[str, str] | None = None
_CHAR_NUMBER_PATTERN = re.compile(r"^char_(\d+)_")


def load_char_table_mapping(gamedata_path: Path, lang: str = "ko_KR") -> None:
    """character_table.json에서 번호→ID 매핑 로드

    스프라이트 ID(char_474_gladiia)와 character_table ID(char_474_glady)가
    다를 수 있으므로, 번호 기준으로 매핑을 구축합니다.
    """
    global _number_to_table_id
    if _number_to_table_id is not None:
        return

    # 후보 경로 (character_mapping.py와 동일한 패턴)
    candidates = [
        gamedata_path / lang / "gamedata" / "excel" / "character_table.json",
        gamedata_path / "gamedata" / "excel" / "character_table.json",
    ]

    char_table_path = None
    for candidate in candidates:
        if candidate.exists():
            char_table_path = candidate
            break

    if char_table_path is None:
        logger.warning("character_table.json을 찾을 수 없어 ID 변환을 건너뜁니다")
        _number_to_table_id = {}
        return

    try:
        with open(char_table_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        mapping: dict[str, str] = {}
        for key in data:
            m = _CHAR_NUMBER_PATTERN.match(key)
            if m:
                mapping[m.group(1)] = key

        _number_to_table_id = mapping
        logger.info(f"character_table 매핑 로드: {len(mapping)}개 캐릭터")
    except Exception as e:
        logger.error(f"character_table 매핑 로드 실패: {e}")
        _number_to_table_id = {}


def resolve_to_table_id(normalized_id: str) -> str:
    """정규화된 ID를 character_table의 실제 ID로 변환

    스프라이트 이름이 character_table 이름과 다른 경우 번호 기반으로 매핑.
    예: char_474_gladiia → char_474_glady

    NPC ID는 변환하지 않습니다.
    """
    if _number_to_table_id is None or not _number_to_table_id:
        return normalized_id

    # char_ 접두사가 아니면 (NPC 등) 그대로 반환
    if not normalized_id.startswith("char_") or "_npc_" in normalized_id:
        return normalized_id

    # 이미 테이블에 있는 ID면 그대로
    m = _CHAR_NUMBER_PATTERN.match(normalized_id)
    if not m:
        return normalized_id

    number = m.group(1)
    table_id = _number_to_table_id.get(number)
    if table_id and table_id != normalized_id:
        logger.debug(f"스프라이트 ID 변환: {normalized_id} → {table_id}")
        return table_id

    return normalized_id


class CharacterIdNormalizer:
    """캐릭터 ID 정규화

    스토리 파일의 다양한 ID 형식을 표준화합니다:
    - char_002_amiya_1#6 → char_002_amiya
    - avg_4072_ironmn_1#8$1 → char_4072_ironmn
    - avgnew_112_siege_1#1$1 → char_112_siege
    - avg_npc_012#3 → avg_npc_012 (범용 NPC)
    - npc_003_kalts → npc_003_kalts (고유 NPC)
    """

    # NPC 접두사 패턴
    NPC_PREFIXES = ("avg_npc_", "bavg_npc_", "npc_")

    # 범용 NPC 패턴: avg_npc_숫자 또는 avg_npc_숫자_숫자
    GENERIC_NPC_PATTERN = re.compile(r"^(avg_npc_|bavg_npc_)\d+(_\d+)?$", re.IGNORECASE)

    # 고유 NPC 패턴: npc_숫자_이름 (예: npc_003_kalts)
    NAMED_NPC_PATTERN = re.compile(r"^npc_\d+_[a-z]", re.IGNORECASE)

    def normalize(self, char_id: str) -> str:
        """캐릭터 ID 정규화

        Args:
            char_id: 원본 캐릭터 ID

        Returns:
            정규화된 캐릭터 ID
        """
        char_id = char_id.strip()
        if not char_id:
            return char_id

        lower_id = char_id.lower()

        # NPC인 경우: 접미사 제거 (접두사 변환 안함)
        if self._is_npc_id(lower_id):
            # #숫자, $숫자 제거 (표정/포즈 변형)
            char_id = re.sub(r"[#$]\d+", "", char_id)
            # _숫자 제거 (끝에 있는 경우, 인스턴스 번호, 1자리만)
            char_id = re.sub(r"_\d$", "", char_id)
            return char_id

        # 플레이어블 캐릭터: 접두사 변환
        if lower_id.startswith("avgnew_"):
            char_id = "char_" + char_id[7:]
        elif lower_id.startswith("avg_"):
            char_id = "char_" + char_id[4:]

        # 접미사 제거 (중간에 있는 것도 제거)
        # 1. #숫자, $숫자 제거 (위치 무관)
        char_id = re.sub(r"[#$]\d+", "", char_id)
        # 2. _숫자 제거 (끝에 있는 경우, 인스턴스 번호, 1자리만)
        char_id = re.sub(r"_\d$", "", char_id)
        # 3. _ex 제거 (확장 스프라이트)
        char_id = re.sub(r"_ex$", "", char_id)

        return char_id

    def _is_npc_id(self, lower_id: str) -> bool:
        """NPC ID 여부 확인"""
        return any(lower_id.startswith(prefix) for prefix in self.NPC_PREFIXES)

    def is_generic_npc(self, char_id: str) -> bool:
        """범용 NPC 여부 확인

        범용 NPC는 여러 캐릭터에 재사용되므로 매핑에서 제외해야 합니다.
        예: avg_npc_012, avg_npc_005_1

        Args:
            char_id: 정규화된 캐릭터 ID

        Returns:
            범용 NPC면 True
        """
        return bool(self.GENERIC_NPC_PATTERN.match(char_id.lower()))

    def is_named_npc(self, char_id: str) -> bool:
        """고유 NPC 여부 확인

        고유 NPC는 특정 캐릭터를 나타내므로 매핑에 사용할 수 있습니다.
        예: npc_003_kalts (켈시), npc_007_closure (클로저)

        Args:
            char_id: 정규화된 캐릭터 ID

        Returns:
            고유 NPC면 True
        """
        return bool(self.NAMED_NPC_PATTERN.match(char_id.lower()))

    def is_playable(self, char_id: str) -> bool:
        """플레이어블 캐릭터 여부 확인

        Args:
            char_id: 정규화된 캐릭터 ID

        Returns:
            플레이어블 캐릭터면 True
        """
        lower_id = char_id.lower()
        # char_로 시작하고 npc가 아닌 경우
        return lower_id.startswith("char_") and "_npc_" not in lower_id


# 모듈 레벨 싱글톤 인스턴스
_normalizer: CharacterIdNormalizer | None = None


def get_normalizer() -> CharacterIdNormalizer:
    """싱글톤 정규화 인스턴스 반환"""
    global _normalizer
    if _normalizer is None:
        _normalizer = CharacterIdNormalizer()
    return _normalizer


def normalize_char_id(char_id: str) -> str:
    """캐릭터 ID 정규화 (편의 함수)"""
    return get_normalizer().normalize(char_id)
