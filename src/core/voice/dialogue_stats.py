"""캐릭터별 대사 통계 모듈

모든 스토리에서 캐릭터별 대사 개수를 계산하고 캐시합니다.
"""

import json
import logging
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class CharacterStats:
    """캐릭터 대사 통계"""

    char_id: str  # 캐릭터 ID (None은 "narrator"로 저장)
    dialogue_count: int  # 총 대사 수
    episode_count: int  # 등장 에피소드 수


class DialogueStatsManager:
    """대사 통계 관리자

    전체 스토리를 스캔하여 캐릭터별 대사 수를 계산하고 캐시합니다.
    """

    CACHE_VERSION = 1

    def __init__(self, data_path: Path, cache_path: Optional[Path] = None):
        """
        Args:
            data_path: gamedata, gamedata_yostar 포함 경로
            cache_path: 캐시 파일 경로 (기본: data_path/cache/dialogue_stats.json)
        """
        self.data_path = Path(data_path)
        self.cache_path = cache_path or (self.data_path / "cache" / "dialogue_stats.json")

        self._stats: dict[str, CharacterStats] = {}
        self._loaded = False

    def get_stats(self, lang: str = "ko_KR") -> dict[str, CharacterStats]:
        """캐릭터별 대사 통계 반환

        캐시가 있으면 캐시에서 로드하고, 없으면 계산합니다.
        """
        if not self._loaded:
            if self.cache_path.exists():
                self._load_cache()
            else:
                self._calculate_stats(lang)
                self._save_cache()
            self._loaded = True

        return self._stats

    def get_dialogue_count(self, char_id: Optional[str], lang: str = "ko_KR") -> int:
        """특정 캐릭터의 대사 수 반환"""
        stats = self.get_stats(lang)
        key = char_id or "narrator"
        if key in stats:
            return stats[key].dialogue_count
        return 0

    def rebuild_stats(self, lang: str = "ko_KR") -> dict[str, CharacterStats]:
        """통계 재계산 (캐시 갱신)"""
        self._loaded = False  # 캐시 무효화
        self._calculate_stats(lang)
        self._save_cache()
        self._loaded = True  # 재계산 완료 표시
        return self._stats

    def _calculate_stats(self, lang: str = "ko_KR") -> None:
        """전체 스토리에서 대사 통계 계산"""
        from ..story.loader import StoryLoader

        logger.info("대사 통계 계산 시작...")
        loader = StoryLoader(self.data_path)

        # 캐릭터별 집계
        dialogue_counts: dict[str, int] = {}  # char_id -> 대사 수
        episode_counts: dict[str, set[str]] = {}  # char_id -> 에피소드 ID 집합

        # 모든 스토리 그룹 순회
        all_groups = loader.load_all_story_groups(lang)
        total_groups = len(all_groups)

        for idx, (group_id, group) in enumerate(all_groups.items()):
            if (idx + 1) % 50 == 0:
                logger.info(f"진행: {idx + 1}/{total_groups} 그룹")

            # 그룹의 모든 에피소드
            episodes = loader.list_episodes_by_group(group_id, lang)

            for ep_info in episodes:
                episode = loader.load_episode(ep_info["id"], lang)
                if not episode:
                    continue

                for dialogue in episode.dialogues:
                    # speaker_id 정규화 (None은 "narrator")
                    char_key = dialogue.speaker_id or "narrator"

                    # 대사 수 집계
                    dialogue_counts[char_key] = dialogue_counts.get(char_key, 0) + 1

                    # 에피소드 집계
                    if char_key not in episode_counts:
                        episode_counts[char_key] = set()
                    episode_counts[char_key].add(ep_info["id"])

        # CharacterStats 객체로 변환
        self._stats = {}
        for char_id, count in dialogue_counts.items():
            self._stats[char_id] = CharacterStats(
                char_id=char_id,
                dialogue_count=count,
                episode_count=len(episode_counts.get(char_id, set())),
            )

        logger.info(f"대사 통계 계산 완료: {len(self._stats)}개 캐릭터")

    def _load_cache(self) -> None:
        """캐시 파일에서 로드"""
        try:
            with open(self.cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 버전 확인
            if data.get("version") != self.CACHE_VERSION:
                logger.warning("캐시 버전 불일치, 재계산 필요")
                return

            self._stats = {}
            for char_id, stat_data in data.get("stats", {}).items():
                self._stats[char_id] = CharacterStats(**stat_data)

            logger.info(f"대사 통계 캐시 로드: {len(self._stats)}개 캐릭터")

        except Exception as e:
            logger.warning(f"캐시 로드 실패: {e}")
            self._stats = {}

    def _save_cache(self) -> None:
        """캐시 파일에 저장"""
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)

            data = {
                "version": self.CACHE_VERSION,
                "stats": {
                    char_id: asdict(stats)
                    for char_id, stats in self._stats.items()
                },
            }

            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.info(f"대사 통계 캐시 저장: {self.cache_path}")

        except Exception as e:
            logger.warning(f"캐시 저장 실패: {e}")
