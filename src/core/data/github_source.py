"""GitHub 레포지토리 기반 게임 데이터 소스

기존 GamedataUpdater를 감싸는 어댑터
"""

from pathlib import Path
from typing import Awaitable, Callable, Optional, Union

from .gamedata_source import GamedataSource
from .gamedata_updater import GamedataUpdater, UpdateProgress


class GithubGamedataSource(GamedataSource):
    """GitHub 레포지토리에서 게임 데이터를 다운로드하는 소스"""

    source_type = "github"

    def __init__(
        self,
        data_root: str | Path,
        repo: str = "ArknightsAssets/ArknightsGamedata",
        branch: str = "master",
    ):
        super().__init__(data_root)
        self._updater = GamedataUpdater(data_root, repo, branch)

    async def update(
        self,
        server: str = "kr",
        on_progress: Optional[
            Callable[[UpdateProgress], Union[None, Awaitable[None]]]
        ] = None,
    ) -> bool:
        result = await self._updater.update(server, on_progress)
        if result:
            # source 필드 포함된 메타 정보 덮어쓰기
            self._save_update_info(server)
        return result

    def cancel(self):
        self._updater.cancel()
