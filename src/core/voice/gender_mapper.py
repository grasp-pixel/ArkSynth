"""캐릭터 성별 매핑 관리

handbook_info_table.json에서 성별 정보를 추출하여 캐싱
"""

import json
import re
from pathlib import Path


class GenderMapper:
    """캐릭터 성별 매핑

    게임 데이터의 handbook_info_table.json에서 성별 정보 추출
    """

    def __init__(self, gamedata_path: str | Path):
        """
        Args:
            gamedata_path: ArknightsGameData 경로 (data/gamedata)
        """
        self.gamedata_path = Path(gamedata_path)
        self._gender_cache: dict[str, str] | None = None
        self._cache_path = self.gamedata_path.parent / "cache" / "character_genders.json"

    def _get_handbook_path(self) -> Path | None:
        """handbook_info_table.json 경로 반환"""
        candidates = [
            self.gamedata_path / "kr" / "gamedata" / "excel" / "handbook_info_table.json",
            self.gamedata_path / "gamedata" / "excel" / "handbook_info_table.json",
        ]

        for path in candidates:
            if path.exists():
                return path
        return None

    def _extract_gender_from_text(self, text: str) -> str | None:
        """스토리 텍스트에서 성별 추출

        형식: [성별] 여 또는 [성별] 남
        """
        match = re.search(r"\[성별\]\s*(여|남)", text)
        if match:
            return "female" if match.group(1) == "여" else "male"
        return None

    def _load_from_handbook(self) -> dict[str, str]:
        """handbook_info_table.json에서 모든 캐릭터 성별 추출"""
        handbook_path = self._get_handbook_path()
        if not handbook_path:
            return {}

        with open(handbook_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        genders = {}
        handbook_dict = data.get("handbookDict", {})

        for char_id, char_data in handbook_dict.items():
            story_audio = char_data.get("storyTextAudio", [])

            for story in story_audio:
                if story.get("storyTitle") == "기본정보":
                    stories = story.get("stories", [])
                    if stories:
                        text = stories[0].get("storyText", "")
                        gender = self._extract_gender_from_text(text)
                        if gender:
                            genders[char_id] = gender
                    break

        return genders

    def _load_cache(self) -> dict[str, str] | None:
        """캐시 파일 로드"""
        if self._cache_path.exists():
            try:
                with open(self._cache_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return None

    def _save_cache(self, genders: dict[str, str]) -> None:
        """캐시 파일 저장"""
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._cache_path, "w", encoding="utf-8") as f:
            json.dump(genders, f, ensure_ascii=False, indent=2)

    def load_genders(self, force_refresh: bool = False) -> dict[str, str]:
        """모든 캐릭터 성별 로드

        Args:
            force_refresh: True면 캐시 무시하고 새로 추출

        Returns:
            dict[str, str]: {char_id: "male"|"female"} 매핑
        """
        if self._gender_cache is not None and not force_refresh:
            return self._gender_cache

        # 캐시 파일 시도
        if not force_refresh:
            cached = self._load_cache()
            if cached:
                self._gender_cache = cached
                return cached

        # handbook에서 추출
        genders = self._load_from_handbook()

        # 캐시 저장
        if genders:
            self._save_cache(genders)

        self._gender_cache = genders
        return genders

    def get_gender(self, char_id: str) -> str | None:
        """캐릭터 성별 조회

        Args:
            char_id: 캐릭터 ID

        Returns:
            "male", "female", 또는 None (정보 없음)
        """
        genders = self.load_genders()
        return genders.get(char_id)

    def get_characters_by_gender(self, gender: str) -> list[str]:
        """특정 성별의 캐릭터 목록

        Args:
            gender: "male" 또는 "female"

        Returns:
            list[str]: 캐릭터 ID 목록
        """
        genders = self.load_genders()
        return [char_id for char_id, g in genders.items() if g == gender]

    def clear_cache(self) -> None:
        """캐시 초기화"""
        self._gender_cache = None
        if self._cache_path.exists():
            self._cache_path.unlink()
