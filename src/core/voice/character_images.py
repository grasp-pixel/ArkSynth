"""캐릭터 이미지 URL 제공 및 로컬 캐싱

fexli/ArknightsResource에서 캐릭터 이미지 다운로드
로컬 캐시가 있으면 로컬 파일 사용
"""

import json
import logging
import httpx
from pathlib import Path
from dataclasses import dataclass
from typing import Callable

logger = logging.getLogger(__name__)

# fexli/ArknightsResource - 자동 업데이트되는 아크나이츠 에셋 리포지토리
RESOURCE_BASE_URL = "https://raw.githubusercontent.com/fexli/ArknightsResource/main"


@dataclass
class CharacterImages:
    """캐릭터 이미지 URL 모음"""

    char_id: str
    avatar_url: str | None = None  # 얼굴 아바타 (avatar 폴더)
    portrait_url: str | None = None  # 스탠딩 일러스트 (charpack 폴더)
    avatar_cached: bool = False
    portrait_cached: bool = False


@dataclass
class DownloadProgress:
    """다운로드 진행 상태"""

    total: int
    completed: int
    current_char_id: str | None = None
    error: str | None = None

    @property
    def progress_percent(self) -> float:
        if self.total == 0:
            return 0.0
        return (self.completed / self.total) * 100


class CharacterImageProvider:
    """캐릭터 이미지 URL 제공

    skin_table.json에서 avatarId, portraitId를 추출하여 URL 생성
    로컬 캐시가 있으면 로컬 파일 경로 반환
    """

    def __init__(self, gamedata_path: str | Path, cache_path: str | Path | None = None):
        """
        Args:
            gamedata_path: ArknightsGameData 경로 (data/gamedata)
            cache_path: 이미지 캐시 기본 경로 (기본: data/cache)
        """
        self.gamedata_path = Path(gamedata_path)
        self._avatar_mapping_cache: dict[str, str] | None = None

        # 캐시 경로 설정 (avatars: 얼굴, portraits: 스탠딩)
        base_cache = Path(cache_path) if cache_path else self.gamedata_path.parent / "cache"
        self.avatar_cache_path = base_cache / "avatars"  # 얼굴 이미지
        self.portrait_cache_path = base_cache / "portraits"  # 스탠딩 이미지
        # 하위 호환성
        self.cache_path = self.portrait_cache_path

    def _get_skin_table_path(self) -> Path | None:
        """skin_table.json 경로 반환"""
        candidates = [
            self.gamedata_path / "kr" / "gamedata" / "excel" / "skin_table.json",
            self.gamedata_path / "gamedata" / "excel" / "skin_table.json",
        ]

        for path in candidates:
            if path.exists():
                return path
        return None

    def _load_avatar_mapping(self) -> dict[str, str]:
        """skin_table.json에서 캐릭터 ID 목록 추출

        Returns:
            dict[str, str]: {char_id: char_id} 매핑 (fexli에서는 char_id 직접 사용)
        """
        if self._avatar_mapping_cache is not None:
            return self._avatar_mapping_cache

        skin_path = self._get_skin_table_path()
        if not skin_path:
            return {}

        with open(skin_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        avatars = {}
        char_skins = data.get("charSkins", {})

        for skin_id, skin_data in char_skins.items():
            char_id = skin_data.get("charId")
            if not char_id:
                continue

            # 기본 스킨만 수집 (skin_id가 char_id#1 형태)
            if skin_id == f"{char_id}#1":
                avatars[char_id] = char_id

        self._avatar_mapping_cache = avatars
        return avatars

    # === 캐시 경로 조회 ===

    def _get_cached_path(self, char_id: str, image_type: str = "portrait") -> Path | None:
        """캐시된 이미지 경로 반환

        Args:
            char_id: 캐릭터 ID
            image_type: "avatar" (얼굴) 또는 "portrait" (스탠딩)

        Returns:
            Path or None: 캐시된 이미지 경로 (존재하면)
        """
        cache_dir = self.avatar_cache_path if image_type == "avatar" else self.portrait_cache_path
        img_path = cache_dir / f"{char_id}.png"
        return img_path if img_path.exists() else None

    def is_avatar_cached(self, char_id: str) -> bool:
        """얼굴 아바타가 캐시되어 있는지 확인"""
        return self._get_cached_path(char_id, "avatar") is not None

    def is_portrait_cached(self, char_id: str) -> bool:
        """스탠딩 이미지가 캐시되어 있는지 확인"""
        return self._get_cached_path(char_id, "portrait") is not None

    def get_cached_avatar_count(self) -> int:
        """캐시된 얼굴 아바타 이미지 수"""
        if not self.avatar_cache_path.exists():
            return 0
        return len(list(self.avatar_cache_path.glob("*.png")))

    def get_cached_portrait_count(self) -> int:
        """캐시된 스탠딩 이미지 수"""
        if not self.portrait_cache_path.exists():
            return 0
        return len(list(self.portrait_cache_path.glob("*.png")))

    # === 원격 URL 생성 ===

    def get_remote_avatar_url(self, char_id: str) -> str | None:
        """원격 얼굴 아바타 URL (다운로드용)"""
        avatars = self._load_avatar_mapping()
        if char_id not in avatars:
            return None
        # fexli/ArknightsResource: avatar/ASSISTANT/{char_id}.png
        return f"{RESOURCE_BASE_URL}/avatar/ASSISTANT/{char_id}.png"

    def get_remote_portrait_url(self, char_id: str) -> str | None:
        """원격 스탠딩 이미지 URL (다운로드용)"""
        avatars = self._load_avatar_mapping()
        if char_id not in avatars:
            return None
        # fexli/ArknightsResource: charpack/{char_id}_1.png
        return f"{RESOURCE_BASE_URL}/charpack/{char_id}_1.png"

    # === 캐시된 이미지 목록 ===

    def get_cached_avatars(self) -> set[str]:
        """캐시된 얼굴 아바타 char_id 목록"""
        if not self.avatar_cache_path.exists():
            return set()
        return {p.stem for p in self.avatar_cache_path.glob("*.png")}

    def get_cached_portraits(self) -> set[str]:
        """캐시된 스탠딩 이미지 char_id 목록"""
        if not self.portrait_cache_path.exists():
            return set()
        return {p.stem for p in self.portrait_cache_path.glob("*.png")}

    def get_images(self, char_id: str) -> CharacterImages:
        """캐릭터 이미지 상태 반환"""
        avatar_cached = self.is_avatar_cached(char_id)
        portrait_cached = self.is_portrait_cached(char_id)

        return CharacterImages(
            char_id=char_id,
            avatar_url=self.get_remote_avatar_url(char_id),
            portrait_url=self.get_remote_portrait_url(char_id),
            avatar_cached=avatar_cached,
            portrait_cached=portrait_cached,
        )

    def get_all_char_ids(self) -> list[str]:
        """모든 캐릭터 ID 목록"""
        return list(self._load_avatar_mapping().keys())

    # === 파일 경로 (API 서빙용) ===

    def get_avatar_file_path(self, char_id: str) -> Path | None:
        """캐시된 얼굴 아바타 파일 경로 (API 서빙용)"""
        return self._get_cached_path(char_id, "avatar")

    def get_portrait_file_path(self, char_id: str) -> Path | None:
        """캐시된 스탠딩 이미지 파일 경로 (API 서빙용)"""
        return self._get_cached_path(char_id, "portrait")

    async def download_image(self, char_id: str, image_type: str = "portrait") -> bool:
        """단일 이미지 다운로드

        Args:
            char_id: 캐릭터 ID
            image_type: "avatar" (얼굴) 또는 "portrait" (스탠딩)

        Returns:
            성공 여부
        """
        if image_type == "avatar":
            url = self.get_remote_avatar_url(char_id)
            cache_dir = self.avatar_cache_path
        else:
            url = self.get_remote_portrait_url(char_id)
            cache_dir = self.portrait_cache_path

        if not url:
            return False

        cache_dir.mkdir(parents=True, exist_ok=True)
        output_path = cache_dir / f"{char_id}.png"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    output_path.write_bytes(response.content)
                    return True
                else:
                    logger.warning(f"{image_type} 다운로드 실패 ({char_id}): HTTP {response.status_code}")
                    return False
        except Exception as e:
            logger.error(f"{image_type} 다운로드 오류 ({char_id}): {e}")
            return False

    # 하위 호환성
    async def download_avatar(self, char_id: str) -> bool:
        """단일 스탠딩 이미지 다운로드 (하위 호환성)"""
        return await self.download_image(char_id, "portrait")

    async def download_all_images(
        self,
        char_ids: list[str] | None = None,
        image_type: str = "portrait",
        on_progress: Callable[[DownloadProgress], None] | None = None,
        skip_cached: bool = True,
    ) -> DownloadProgress:
        """모든 이미지 다운로드

        Args:
            char_ids: 다운로드할 캐릭터 ID 목록 (None이면 전체)
            image_type: "avatar" (얼굴), "portrait" (스탠딩), "both" (둘 다)
            on_progress: 진행률 콜백
            skip_cached: 이미 캐시된 이미지 스킵

        Returns:
            최종 진행 상태
        """
        avatars = self._load_avatar_mapping()

        if char_ids is None:
            char_ids = list(avatars.keys())

        # 다운로드할 (char_id, type) 쌍 생성
        tasks: list[tuple[str, str]] = []
        if image_type in ("avatar", "both"):
            for cid in char_ids:
                if not skip_cached or not self.is_avatar_cached(cid):
                    tasks.append((cid, "avatar"))
        if image_type in ("portrait", "both"):
            for cid in char_ids:
                if not skip_cached or not self.is_portrait_cached(cid):
                    tasks.append((cid, "portrait"))

        progress = DownloadProgress(total=len(tasks), completed=0)

        if progress.total == 0:
            return progress

        self.avatar_cache_path.mkdir(parents=True, exist_ok=True)
        self.portrait_cache_path.mkdir(parents=True, exist_ok=True)

        async with httpx.AsyncClient(timeout=30.0) as client:
            for char_id, img_type in tasks:
                progress.current_char_id = f"{char_id}:{img_type}"

                if img_type == "avatar":
                    url = self.get_remote_avatar_url(char_id)
                    cache_dir = self.avatar_cache_path
                else:
                    url = self.get_remote_portrait_url(char_id)
                    cache_dir = self.portrait_cache_path

                if not url:
                    progress.completed += 1
                    if on_progress:
                        on_progress(progress)
                    continue

                try:
                    response = await client.get(url)
                    if response.status_code == 200:
                        output_path = cache_dir / f"{char_id}.png"
                        output_path.write_bytes(response.content)
                except Exception as e:
                    logger.warning(f"{img_type} 다운로드 실패 ({char_id}): {e}")

                progress.completed += 1
                if on_progress:
                    on_progress(progress)

        progress.current_char_id = None
        return progress

    def clear_cache(self, image_type: str = "both") -> int:
        """이미지 캐시 삭제

        Args:
            image_type: "avatar", "portrait", "both"

        Returns:
            삭제된 파일 수
        """
        deleted = 0
        dirs = []
        if image_type in ("avatar", "both"):
            dirs.append(self.avatar_cache_path)
        if image_type in ("portrait", "both"):
            dirs.append(self.portrait_cache_path)

        for cache_dir in dirs:
            if not cache_dir.exists():
                continue
            for png_file in cache_dir.glob("*.png"):
                try:
                    png_file.unlink()
                    deleted += 1
                except Exception as e:
                    logger.warning(f"캐시 삭제 실패 ({png_file}): {e}")

        return deleted

    # 하위 호환성
    def clear_avatar_cache(self) -> int:
        """아바타 캐시 삭제 (하위 호환성 - 실제로는 portrait 캐시)"""
        return self.clear_cache("portrait")

    def clear_mapping_cache(self) -> None:
        """매핑 캐시 초기화 (메모리)"""
        self._avatar_mapping_cache = None
