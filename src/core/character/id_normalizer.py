"""캐릭터 ID 정규화 모듈

프로젝트 전체에서 단일 ID 정규화 기준을 사용합니다.
기존 character_name_mapper.py, loader.py, parser.py의 정규화 로직을 통합했습니다.
"""

import re


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
