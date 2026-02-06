"""공식 게임 데이터 제공자

character_table.json과 story_variables.json에서 공식 캐릭터 정보를 추출합니다.
공식 데이터에 있는 이름만 신뢰하는 화이트리스트 방식을 사용합니다.
"""

import json
import logging
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)


class OfficialDataProvider:
    """공식 게임 데이터 제공자

    데이터 소스:
    - character_table.json: 캐릭터 ID와 공식 이름
    - story_variables.json: avatar_* 매핑 (스토리 변수)
    - character_aliases.json: 사용자 정의 별칭 (수동 추가)
    """

    def __init__(self, data_path: Path | str | None = None):
        """초기화

        Args:
            data_path: 데이터 디렉토리 경로. None이면 config에서 로드
        """
        if data_path is None:
            from ..backend.config import config

            data_path = Path(config.data_path)
        else:
            data_path = Path(data_path)

        self._data_path = data_path
        self._gamedata_path = data_path / "gamedata" / "kr" / "gamedata"

        # 캐시
        self._character_table: dict[str, dict] | None = None
        self._story_variables: dict[str, str] | None = None
        self._user_aliases: dict[str, str] | None = None

        # 이름 → char_id 역매핑 캐시
        self._name_to_char_id: dict[str, str] | None = None
        self._official_names: set[str] | None = None

    def _load_character_table(self) -> dict[str, dict]:
        """character_table.json 로드"""
        if self._character_table is not None:
            return self._character_table

        table_path = self._gamedata_path / "excel" / "character_table.json"
        if not table_path.exists():
            logger.warning(f"캐릭터 테이블 없음: {table_path}")
            self._character_table = {}
            return self._character_table

        try:
            with open(table_path, "r", encoding="utf-8") as f:
                self._character_table = json.load(f)
                logger.debug(f"캐릭터 테이블 로드: {len(self._character_table)}개")
        except Exception as e:
            logger.error(f"캐릭터 테이블 로드 실패: {e}")
            self._character_table = {}

        return self._character_table

    def _load_story_variables(self) -> dict[str, str]:
        """story_variables.json 로드"""
        if self._story_variables is not None:
            return self._story_variables

        vars_path = self._gamedata_path / "story" / "story_variables.json"
        if not vars_path.exists():
            logger.warning(f"스토리 변수 파일 없음: {vars_path}")
            self._story_variables = {}
            return self._story_variables

        try:
            with open(vars_path, "r", encoding="utf-8") as f:
                self._story_variables = json.load(f)
                logger.debug(f"스토리 변수 로드: {len(self._story_variables)}개")
        except Exception as e:
            logger.error(f"스토리 변수 로드 실패: {e}")
            self._story_variables = {}

        return self._story_variables

    def _load_user_aliases(self) -> dict[str, str]:
        """character_aliases.json 로드 (사용자 정의 별칭)"""
        if self._user_aliases is not None:
            return self._user_aliases

        aliases_path = self._data_path / "character_aliases.json"
        if not aliases_path.exists():
            logger.debug(f"사용자 별칭 파일 없음: {aliases_path}")
            self._user_aliases = {}
            return self._user_aliases

        try:
            with open(aliases_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._user_aliases = data.get("aliases", {})
                logger.debug(f"사용자 별칭 로드: {len(self._user_aliases)}개")
        except Exception as e:
            logger.error(f"사용자 별칭 로드 실패: {e}")
            self._user_aliases = {}

        return self._user_aliases

    def _build_name_to_char_id_map(self) -> dict[str, str]:
        """이름 → char_id 역매핑 구축"""
        if self._name_to_char_id is not None:
            return self._name_to_char_id

        self._name_to_char_id = {}
        self._official_names = set()

        char_table = self._load_character_table()

        for char_id, char_data in char_table.items():
            name = char_data.get("name")
            if name:
                self._name_to_char_id[name] = char_id
                self._official_names.add(name)

            # appellation도 추가 (영문명/별칭)
            appellation = char_data.get("appellation")
            if appellation and appellation != name:
                # 이미 있는 이름은 덮어쓰지 않음
                if appellation not in self._name_to_char_id:
                    self._name_to_char_id[appellation] = char_id
                self._official_names.add(appellation)

        logger.debug(f"이름 매핑 구축: {len(self._name_to_char_id)}개")
        return self._name_to_char_id

    def get_char_id_by_name(self, name: str) -> str | None:
        """공식 이름으로 캐릭터 ID 조회

        Args:
            name: 캐릭터 이름 (한글 또는 영문)

        Returns:
            캐릭터 ID 또는 None
        """
        # 1. 사용자 별칭 우선
        aliases = self._load_user_aliases()
        if name in aliases:
            return aliases[name]

        # 2. 공식 데이터에서 조회
        name_map = self._build_name_to_char_id_map()
        return name_map.get(name)

    def get_avatar_mapping(self) -> dict[str, str]:
        """story_variables.json의 avatar_* 매핑 반환

        Returns:
            {avatar_key: char_id} 형식 (예: {"grani": "char_220_grani"})
        """
        story_vars = self._load_story_variables()
        result = {}

        for key, value in story_vars.items():
            if key.startswith("avatar_") and isinstance(value, str):
                # avatar_grani → grani
                short_key = key[7:]  # "avatar_" 제거
                result[short_key] = value

        return result

    def get_all_official_names(self) -> set[str]:
        """모든 공식 캐릭터 이름 반환

        Returns:
            공식 이름 집합
        """
        self._build_name_to_char_id_map()
        return self._official_names or set()

    def is_official_name(self, name: str) -> bool:
        """공식 캐릭터 이름인지 확인

        Args:
            name: 확인할 이름

        Returns:
            공식 이름이면 True
        """
        return name in self.get_all_official_names()

    def get_unconfirmed_names(self, story_names: set[str]) -> set[str]:
        """공식 데이터에 없는 이름 목록 반환 (검토용)

        Args:
            story_names: 스토리에서 발견된 이름 집합

        Returns:
            미확인 이름 집합
        """
        official = self.get_all_official_names()
        aliases = set(self._load_user_aliases().keys())
        confirmed = official | aliases
        return story_names - confirmed

    def get_char_info(self, char_id: str) -> dict | None:
        """캐릭터 정보 조회

        Args:
            char_id: 캐릭터 ID

        Returns:
            캐릭터 정보 딕셔너리 또는 None
        """
        char_table = self._load_character_table()
        return char_table.get(char_id)

    def invalidate_cache(self) -> None:
        """캐시 무효화"""
        self._character_table = None
        self._story_variables = None
        self._user_aliases = None
        self._name_to_char_id = None
        self._official_names = None
        logger.debug("공식 데이터 캐시 무효화")

    def get_all_aliases(self) -> dict[str, str]:
        """모든 사용자 정의 별칭 반환

        Returns:
            {별칭: char_id} 딕셔너리
        """
        return self._load_user_aliases().copy()

    def get_aliases_for_char(self, char_id: str) -> list[str]:
        """특정 캐릭터의 모든 별칭 반환 (역방향 조회)

        Args:
            char_id: 캐릭터 ID

        Returns:
            해당 캐릭터를 가리키는 별칭 목록
        """
        aliases = self._load_user_aliases()
        return [alias for alias, cid in aliases.items() if cid == char_id]

    def add_alias(self, alias: str, char_id: str) -> bool:
        """별칭 추가

        Args:
            alias: 추가할 별칭 (본명, 닉네임 등)
            char_id: 캐릭터 ID

        Returns:
            성공 여부 (이미 존재하면 False)
        """
        aliases = self._load_user_aliases()
        if alias in aliases:
            logger.warning(f"별칭 이미 존재: {alias} → {aliases[alias]}")
            return False

        aliases[alias] = char_id
        self._save_user_aliases(aliases)
        logger.info(f"별칭 추가: {alias} → {char_id}")
        return True

    def remove_alias(self, alias: str) -> bool:
        """별칭 삭제

        Args:
            alias: 삭제할 별칭

        Returns:
            성공 여부 (존재하지 않으면 False)
        """
        aliases = self._load_user_aliases()
        if alias not in aliases:
            logger.warning(f"별칭 없음: {alias}")
            return False

        del aliases[alias]
        self._save_user_aliases(aliases)
        logger.info(f"별칭 삭제: {alias}")
        return True

    def _save_user_aliases(self, aliases: dict[str, str]) -> None:
        """character_aliases.json 저장"""
        aliases_path = self._data_path / "character_aliases.json"

        # 기존 파일 로드 (메타데이터 유지)
        existing = {}
        if aliases_path.exists():
            try:
                with open(aliases_path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            except Exception:
                pass

        # 메타데이터 유지, aliases만 업데이트
        data = {
            "_version": existing.get("_version", 1),
            "_comment": existing.get(
                "_comment",
                "캐릭터 별칭 매핑 (화자 이름 → char_id)",
            ),
            "aliases": aliases,
        }

        # _conflicts가 있으면 유지
        if "_conflicts" in existing:
            data["_conflicts"] = existing["_conflicts"]

        with open(aliases_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        # 캐시 무효화
        self._user_aliases = aliases
        logger.debug(f"사용자 별칭 저장: {len(aliases)}개")


# 모듈 레벨 싱글톤 인스턴스
_provider: OfficialDataProvider | None = None


def get_official_data_provider() -> OfficialDataProvider:
    """싱글톤 공식 데이터 제공자 반환"""
    global _provider
    if _provider is None:
        _provider = OfficialDataProvider()
    return _provider
