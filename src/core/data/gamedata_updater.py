"""게임 데이터 업데이터

GitHub 레포지토리에서 필요한 게임 데이터만 선택적으로 다운로드
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Awaitable, Callable, Optional, Union

import aiohttp

logger = logging.getLogger(__name__)

# 필요한 Excel JSON 파일 목록
NEEDED_EXCEL_FILES = [
    "character_table.json",
    "story_review_table.json",
    "charword_table.json",
    "handbook_info_table.json",
]

# 스토리 폴더 중 제외할 경로
EXCLUDED_STORY_DIRS = {"[uc]info"}

MAX_CONCURRENT_DOWNLOADS = 50


@dataclass
class UpdateProgress:
    """업데이트 진행 상태"""

    stage: str  # checking, downloading, complete, error
    progress: float  # 0.0 ~ 1.0
    message: str
    error: Optional[str] = None


@dataclass
class GamedataStatus:
    """게임 데이터 상태"""

    exists: bool
    path: str
    server: str
    last_updated: Optional[str] = None
    story_count: int = 0


class GamedataUpdater:
    """게임 데이터 업데이터

    GitHub 레포지토리에서 필요한 파일만 선택적으로 다운로드합니다.
    """

    def __init__(
        self,
        data_root: str | Path,
        repo: str = "ArknightsAssets/ArknightsGamedata",
        branch: str = "master",
    ):
        self.data_root = Path(data_root)
        self.gamedata_path = self.data_root / "gamedata"
        self.repo = repo
        self.branch = branch
        self._cancel_flag = False
        self._update_info_path = self.gamedata_path / ".update_info.json"

    @property
    def _api_tree_url(self) -> str:
        return f"https://api.github.com/repos/{self.repo}/git/trees/{self.branch}?recursive=1"

    @property
    def _raw_base_url(self) -> str:
        return f"https://raw.githubusercontent.com/{self.repo}/{self.branch}"

    def get_status(self, server: str = "kr") -> GamedataStatus:
        """현재 게임 데이터 상태 확인"""
        server_path = self.gamedata_path / server
        story_path = server_path / "gamedata" / "story"

        exists = story_path.exists()
        story_count = 0
        last_updated = None

        if exists:
            story_count = sum(1 for _ in story_path.rglob("*.txt"))

        if self._update_info_path.exists():
            try:
                with open(self._update_info_path, "r", encoding="utf-8") as f:
                    info = json.load(f)
                    last_updated = info.get("last_updated")
            except Exception:
                pass

        return GamedataStatus(
            exists=exists,
            path=str(server_path),
            server=server,
            last_updated=last_updated,
            story_count=story_count,
        )

    async def update(
        self,
        server: str = "kr",
        on_progress: Optional[
            Callable[[UpdateProgress], Union[None, Awaitable[None]]]
        ] = None,
    ) -> bool:
        """게임 데이터 업데이트"""
        self._cancel_flag = False

        async def report(
            stage: str, progress: float, message: str, error: str = None
        ):
            if on_progress:
                try:
                    result = on_progress(
                        UpdateProgress(stage, progress, message, error)
                    )
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as e:
                    logger.exception(f"on_progress 콜백 오류: {e}")

        try:
            await report("checking", 0.0, "파일 목록 조회 중...")

            # 1. GitHub API로 파일 트리 조회
            tree = await self._fetch_file_tree()
            if tree is None:
                await report("error", 0.0, "파일 목록 조회 실패", "GitHub API 요청 실패")
                return False

            if self._cancel_flag:
                await report("error", 0.0, "취소됨", "사용자가 취소함")
                return False

            # 2. 필요한 파일 필터링
            files = self._filter_needed_files(tree, server)
            total = len(files)

            if total == 0:
                await report(
                    "error", 0.0, "다운로드할 파일 없음",
                    f"레포지토리에서 {server} 서버 데이터를 찾을 수 없습니다"
                )
                return False

            await report("downloading", 0.05, f"{total}개 파일 다운로드 시작...")
            logger.info(f"다운로드 대상: {total}개 파일 (서버: {server})")

            # 3. 병렬 다운로드
            success = await self._download_files(files, server, total, report)

            if self._cancel_flag:
                await report("error", 0.0, "취소됨", "사용자가 취소함")
                return False

            if not success:
                await report("error", 0.0, "다운로드 실패", "일부 파일 다운로드에 실패했습니다")
                return False

            # 4. 업데이트 정보 저장
            self._save_update_info(server)
            await report("complete", 1.0, f"업데이트 완료! ({total}개 파일)")
            return True

        except asyncio.CancelledError:
            await report("error", 0.0, "취소됨", "작업이 취소되었습니다")
            return False
        except Exception as e:
            logger.exception(f"업데이트 실패: {e}")
            await report("error", 0.0, "업데이트 실패", str(e))
            return False

    def cancel(self):
        """업데이트 취소"""
        self._cancel_flag = True

    async def _fetch_file_tree(self) -> Optional[list[dict]]:
        """GitHub API로 전체 파일 트리 조회"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self._api_tree_url,
                    headers={"Accept": "application/vnd.github.v3+json"},
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as resp:
                    if resp.status != 200:
                        logger.error(f"GitHub API 응답 오류: {resp.status}")
                        return None
                    data = await resp.json()
                    return data.get("tree", [])
        except Exception as e:
            logger.exception(f"GitHub API 요청 실패: {e}")
            return None

    def _filter_needed_files(
        self, tree: list[dict], server: str
    ) -> list[str]:
        """트리에서 필요한 파일 경로만 필터링"""
        needed = []
        excel_prefix = f"{server}/gamedata/excel/"
        story_prefix = f"{server}/gamedata/story/"

        for item in tree:
            if item.get("type") != "blob":
                continue

            path = item["path"]

            # Excel JSON 파일
            if path.startswith(excel_prefix):
                filename = path[len(excel_prefix):]
                if filename in NEEDED_EXCEL_FILES:
                    needed.append(path)
                continue

            # Story 파일 (.txt + story_variables.json)
            if path.startswith(story_prefix):
                rel = path[len(story_prefix):]

                # 제외 디렉토리 체크
                first_dir = rel.split("/")[0] if "/" in rel else ""
                if first_dir in EXCLUDED_STORY_DIRS:
                    continue

                if path.endswith(".txt") or rel == "story_variables.json":
                    needed.append(path)

        return needed

    async def _download_files(
        self,
        files: list[str],
        server: str,
        total: int,
        report,
    ) -> bool:
        """파일들을 병렬로 다운로드"""
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)
        completed = 0
        failed = 0

        async def download_one(session: aiohttp.ClientSession, file_path: str):
            nonlocal completed, failed

            if self._cancel_flag:
                return

            url = f"{self._raw_base_url}/{file_path}"
            local_path = self.gamedata_path / file_path

            try:
                async with semaphore:
                    async with session.get(
                        url, timeout=aiohttp.ClientTimeout(total=120)
                    ) as resp:
                        if resp.status != 200:
                            logger.warning(f"다운로드 실패 ({resp.status}): {file_path}")
                            failed += 1
                            return

                        content = await resp.read()

                local_path.parent.mkdir(parents=True, exist_ok=True)
                local_path.write_bytes(content)

                completed += 1
                if completed % 50 == 0 or completed == total:
                    progress = 0.05 + (completed / total) * 0.90
                    await report(
                        "downloading", progress,
                        f"다운로드 중... ({completed}/{total})"
                    )

            except Exception as e:
                logger.warning(f"다운로드 오류: {file_path} - {e}")
                failed += 1

        connector = aiohttp.TCPConnector(limit=MAX_CONCURRENT_DOWNLOADS)
        async with aiohttp.ClientSession(connector=connector) as session:
            tasks = [download_one(session, f) for f in files]
            await asyncio.gather(*tasks)

        logger.info(f"다운로드 완료: {completed} 성공, {failed} 실패 / {total} 전체")

        # 실패가 전체의 10% 이상이면 실패로 간주
        if failed > total * 0.1:
            return False
        return True

    def _save_update_info(self, server: str):
        """업데이트 정보 저장"""
        self.gamedata_path.mkdir(parents=True, exist_ok=True)

        info = {
            "server": server,
            "repo": self.repo,
            "branch": self.branch,
            "last_updated": datetime.now().isoformat(),
        }

        with open(self._update_info_path, "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=2)
