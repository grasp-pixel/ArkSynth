"""스토리 데이터 로더"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from ..models.story import Character, Episode, StoryCategory, StoryGroup
from .parser import StoryParser


@dataclass
class StoryMeta:
    """스토리 메타데이터"""

    story_id: str
    story_code: str  # "0-1", "1-7" 등
    story_name: str  # "어둠 속에서", "각성" 등
    avg_tag: str  # "작전 전", "작전 후"
    story_txt: str  # 파일 경로
    group_name: str  # "서장", "제1장" 등


class StoryLoader:
    """ArknightsGameData 스토리 로더

    게임 데이터에서 스토리 파일과 캐릭터 정보를 로드
    한국어(ko_KR)를 기본 언어로 사용
    """

    def __init__(self, data_root: str | Path):
        """
        Args:
            data_root: data 폴더 경로 (gamedata, gamedata_yostar 포함)
        """
        self.data_root = Path(data_root)
        self.parser = StoryParser()

        # 언어별 경로 매핑
        self._lang_paths = {
            "ko_KR": self.data_root / "gamedata_yostar" / "ko_KR" / "gamedata",
            "en_US": self.data_root / "gamedata_yostar" / "en_US" / "gamedata",
            "ja_JP": self.data_root / "gamedata_yostar" / "ja_JP" / "gamedata",
            "zh_CN": self.data_root / "gamedata" / "zh_CN" / "gamedata",
        }

        # 캐시
        self._character_cache: dict[str, dict[str, Character]] = {}
        self._episode_index: dict[str, dict[str, Path]] = {}
        self._story_meta_cache: dict[str, dict[str, StoryMeta]] = {}
        self._chapter_names: dict[str, dict[str, str]] = {}
        self._story_groups_cache: dict[str, dict[str, StoryGroup]] = {}
        self._story_review_raw: dict[str, dict] = {}  # 원본 JSON 캐시

    @property
    def available_languages(self) -> list[str]:
        """사용 가능한 언어 목록"""
        return [lang for lang, path in self._lang_paths.items() if path.exists()]

    def get_lang_path(self, lang: str = "ko_KR") -> Path:
        """언어별 게임 데이터 경로"""
        if lang not in self._lang_paths:
            raise ValueError(f"Unsupported language: {lang}")
        path = self._lang_paths[lang]
        if not path.exists():
            raise FileNotFoundError(f"Language data not found: {path}")
        return path

    def load_story_meta(self, lang: str = "ko_KR") -> dict[str, StoryMeta]:
        """스토리 메타데이터 로드 (제목, 코드 등)"""
        if lang in self._story_meta_cache:
            return self._story_meta_cache[lang]

        meta_path = self.get_lang_path(lang) / "excel" / "story_review_table.json"
        if not meta_path.exists():
            self._story_meta_cache[lang] = {}
            return {}

        with open(meta_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        metas = {}
        chapter_names = {}

        for group_id, group_data in data.items():
            group_name = group_data.get("name", group_id)
            chapter_names[group_id] = group_name

            for info in group_data.get("infoUnlockDatas", []):
                story_txt = info.get("storyTxt", "")
                if not story_txt:
                    continue

                # 파일명 추출 (obt/main/level_main_01-01_beg)
                file_stem = Path(story_txt).stem

                meta = StoryMeta(
                    story_id=info.get("storyId", ""),
                    story_code=info.get("storyCode", ""),
                    story_name=info.get("storyName", ""),
                    avg_tag=info.get("avgTag", ""),
                    story_txt=story_txt,
                    group_name=group_name,
                )
                metas[file_stem] = meta

        self._story_meta_cache[lang] = metas
        self._chapter_names[lang] = chapter_names
        return metas

    def load_characters(self, lang: str = "ko_KR") -> dict[str, Character]:
        """캐릭터 정보 로드"""
        if lang in self._character_cache:
            return self._character_cache[lang]

        char_table_path = self.get_lang_path(lang) / "excel" / "character_table.json"

        if not char_table_path.exists():
            self._character_cache[lang] = {}
            return {}

        with open(char_table_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        characters = {}
        for char_id, char_data in data.items():
            name = char_data.get("name", "")
            character = Character(
                char_id=char_id,
                name_ko=name if lang == "ko_KR" else "",
                name_cn=name if lang == "zh_CN" else "",
            )
            characters[char_id] = character

        self._character_cache[lang] = characters
        return characters

    def get_character(self, char_id: str, lang: str = "ko_KR") -> Character | None:
        """캐릭터 ID로 캐릭터 정보 조회"""
        characters = self.load_characters(lang)

        if char_id in characters:
            return characters[char_id]

        normalized_id = self._normalize_char_id(char_id)
        if normalized_id in characters:
            return characters[normalized_id]

        return None

    def _normalize_char_id(self, char_id: str) -> str:
        """캐릭터 ID 정규화"""
        char_id = char_id.strip()
        char_id = re.sub(r"#\d+$", "", char_id)
        char_id = re.sub(r"_\d+$", "", char_id)
        char_id = re.sub(r"_ex$", "", char_id)
        return char_id

    def build_episode_index(self, lang: str = "ko_KR") -> dict[str, Path]:
        """에피소드 인덱스 구축

        [uc]info 폴더는 스토리 설명만 포함하므로 제외
        실제 스토리 대사는 obt/, activities/ 폴더에 있음
        """
        if lang in self._episode_index:
            return self._episode_index[lang]

        story_root = self.get_lang_path(lang) / "story"
        index = {}

        # 제외할 폴더 패턴
        exclude_patterns = ["[uc]info", "[uc]"]

        for category_dir in story_root.iterdir():
            if not category_dir.is_dir():
                continue

            # [uc]info 등 메타 폴더 제외
            if any(pattern in category_dir.name for pattern in exclude_patterns):
                continue

            for txt_file in category_dir.rglob("*.txt"):
                episode_id = txt_file.stem
                index[episode_id] = txt_file

        self._episode_index[lang] = index
        return index

    def list_main_episodes(self, lang: str = "ko_KR") -> list[dict]:
        """메인 스토리 에피소드 목록 (메타데이터 포함)

        Returns:
            list[dict]: [{id, code, name, tag, chapter}, ...]
        """
        index = self.build_episode_index(lang)
        metas = self.load_story_meta(lang)

        # 메인 스토리만 필터링
        main_episodes = []
        for episode_id, path in index.items():
            if "main" not in str(path):
                continue

            # level_main_01-07_beg -> 1-7
            code = self._extract_episode_code(episode_id)
            tag = "작전 전" if episode_id.endswith("_beg") else "작전 후"

            # 메타데이터에서 제목 가져오기
            meta = metas.get(episode_id)
            if meta:
                name = meta.story_name
                chapter = meta.group_name
            else:
                name = ""
                chapter = self._guess_chapter_name(episode_id)

            main_episodes.append(
                {
                    "id": episode_id,
                    "code": code,
                    "name": name,
                    "tag": tag,
                    "chapter": chapter,
                    "display_name": f"{code} {name}" if name else code,
                }
            )

        # 코드 순으로 정렬
        main_episodes.sort(key=lambda x: self._episode_sort_key(x["id"]))
        return main_episodes

    def _extract_episode_code(self, episode_id: str) -> str:
        """에피소드 ID에서 코드 추출

        level_main_01-07_beg -> 1-7
        level_main_10-01_end -> 10-1
        """
        match = re.search(r"level_main_(\d+)-(\d+)", episode_id)
        if match:
            chapter = int(match.group(1))
            stage = int(match.group(2))
            return f"{chapter}-{stage}"
        return episode_id

    def _guess_chapter_name(self, episode_id: str) -> str:
        """에피소드 ID로 챕터 이름 추측"""
        match = re.search(r"level_main_(\d+)", episode_id)
        if match:
            chapter_num = int(match.group(1))
            if chapter_num == 0:
                return "서장"
            return f"제{chapter_num}장"
        return ""

    def _episode_sort_key(self, episode_id: str):
        """에피소드 정렬 키"""
        match = re.search(r"level_main_(\d+)-(\d+)_(beg|end)", episode_id)
        if match:
            chapter = int(match.group(1))
            stage = int(match.group(2))
            order = 0 if match.group(3) == "beg" else 1
            return (chapter, stage, order)
        return (999, 999, 0)

    def load_episode(self, episode_id: str, lang: str = "ko_KR") -> Episode | None:
        """에피소드 로드"""
        index = self.build_episode_index(lang)

        if episode_id not in index:
            return None

        filepath = index[episode_id]
        episode = self.parser.parse_file(filepath)

        # 메타데이터로 제목 보강
        metas = self.load_story_meta(lang)
        meta = metas.get(episode_id)
        if meta and not episode.title:
            episode.title = f"{meta.story_code} {meta.story_name}"

        return episode

    def iter_episodes(
        self, category: str | None = None, lang: str = "ko_KR"
    ) -> Iterator[Episode]:
        """에피소드 순회"""
        index = self.build_episode_index(lang)

        for episode_id, path in index.items():
            if category and category not in str(path):
                continue

            episode = self.load_episode(episode_id, lang)
            if episode:
                yield episode

    def search_dialogue(
        self, text: str, episode_id: str, lang: str = "ko_KR"
    ) -> list[tuple[int, float]]:
        """에피소드 내에서 텍스트 검색"""
        from difflib import SequenceMatcher

        episode = self.load_episode(episode_id, lang)
        if not episode:
            return []

        results = []
        for i, dialogue in enumerate(episode.dialogues):
            similarity = SequenceMatcher(None, text, dialogue.text).ratio()
            if similarity > 0.3:
                results.append((i, similarity))

        results.sort(key=lambda x: x[1], reverse=True)
        return results

    # ========== 스토리 그룹/카테고리 관련 메서드 ==========

    def _load_story_review_raw(self, lang: str = "ko_KR") -> dict:
        """story_review_table.json 원본 로드"""
        if lang in self._story_review_raw:
            return self._story_review_raw[lang]

        meta_path = self.get_lang_path(lang) / "excel" / "story_review_table.json"
        if not meta_path.exists():
            self._story_review_raw[lang] = {}
            return {}

        with open(meta_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self._story_review_raw[lang] = data
        return data

    def _classify_category(self, entry_type: str, group_id: str) -> StoryCategory:
        """entryType과 group_id로 카테고리 분류"""
        if entry_type == "MAINLINE":
            return StoryCategory.MAINLINE
        elif entry_type == "MINI_ACTIVITY":
            return StoryCategory.MINI
        elif "side" in group_id.lower():
            return StoryCategory.SIDE
        elif entry_type == "ACTIVITY":
            return StoryCategory.EVENT
        return StoryCategory.OTHER

    def _get_sort_key(self, group_id: str, entry_type: str) -> int:
        """그룹 정렬 키 계산"""
        # 메인 스토리: main_0 -> 0, main_1 -> 1 ...
        if entry_type == "MAINLINE":
            match = re.search(r"main_(\d+)", group_id)
            if match:
                return int(match.group(1))
        # 이벤트: 시작 시간 기반 정렬은 복잡하므로 ID 기반
        return 0

    def load_all_story_groups(self, lang: str = "ko_KR") -> dict[str, StoryGroup]:
        """전체 스토리 그룹 로드

        story_review_table.json의 각 항목이 하나의 스토리 그룹
        """
        if lang in self._story_groups_cache:
            return self._story_groups_cache[lang]

        raw_data = self._load_story_review_raw(lang)
        groups = {}

        for group_id, group_data in raw_data.items():
            entry_type = group_data.get("entryType", "")
            act_type = group_data.get("actType", "")
            name = group_data.get("name", group_id)
            episodes = group_data.get("infoUnlockDatas", [])

            category = self._classify_category(entry_type, group_id)
            sort_key = self._get_sort_key(group_id, entry_type)

            groups[group_id] = StoryGroup(
                id=group_id,
                name=name,
                category=category,
                entry_type=entry_type,
                act_type=act_type,
                episode_count=len(episodes),
                sort_key=sort_key,
            )

        self._story_groups_cache[lang] = groups
        return groups

    def list_groups_by_category(
        self, category: StoryCategory, lang: str = "ko_KR"
    ) -> list[StoryGroup]:
        """카테고리별 스토리 그룹 목록"""
        all_groups = self.load_all_story_groups(lang)

        filtered = [g for g in all_groups.values() if g.category == category]

        # 메인 스토리는 sort_key로 정렬, 나머지는 이름순
        if category == StoryCategory.MAINLINE:
            filtered.sort(key=lambda g: g.sort_key)
        else:
            filtered.sort(key=lambda g: g.name)

        return filtered

    def list_episodes_by_group(
        self, group_id: str, lang: str = "ko_KR"
    ) -> list[dict]:
        """스토리 그룹의 에피소드 목록"""
        raw_data = self._load_story_review_raw(lang)

        if group_id not in raw_data:
            return []

        group_data = raw_data[group_id]
        episodes = []

        for info in group_data.get("infoUnlockDatas", []):
            story_txt = info.get("storyTxt", "")
            if not story_txt:
                continue

            file_stem = Path(story_txt).stem

            episodes.append(
                {
                    "id": file_stem,
                    "story_id": info.get("storyId", ""),
                    "code": info.get("storyCode", ""),
                    "name": info.get("storyName", ""),
                    "tag": info.get("avgTag", ""),
                    "story_txt": story_txt,
                    "sort": info.get("storySort", 0),
                }
            )

        # storySort 순으로 정렬
        episodes.sort(key=lambda x: x["sort"])
        return episodes

    def get_category_stats(self, lang: str = "ko_KR") -> dict[str, dict]:
        """카테고리별 통계"""
        all_groups = self.load_all_story_groups(lang)

        stats = {}
        for cat in StoryCategory:
            groups = [g for g in all_groups.values() if g.category == cat]
            total_episodes = sum(g.episode_count for g in groups)
            stats[cat.value] = {
                "group_count": len(groups),
                "episode_count": total_episodes,
            }

        return stats
