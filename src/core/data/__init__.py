"""게임 데이터 관리 모듈"""

from pathlib import Path

from .gamedata_source import GamedataSource
from .gamedata_updater import GamedataStatus, GamedataUpdater, UpdateProgress

__all__ = [
    "GamedataUpdater",
    "GamedataSource",
    "GamedataStatus",
    "UpdateProgress",
    "create_gamedata_source",
]


def create_gamedata_source(
    source_type: str, data_root: str | Path, **kwargs
) -> GamedataSource:
    """설정에 따라 적절한 데이터 소스 인스턴스 생성"""
    if source_type == "arkprts":
        from .arkprts_source import ArkprtsGamedataSource

        return ArkprtsGamedataSource(data_root)
    else:  # "github" (기본값)
        from .github_source import GithubGamedataSource

        return GithubGamedataSource(
            data_root,
            repo=kwargs.get("repo", "ArknightsAssets/ArknightsGamedata"),
            branch=kwargs.get("branch", "master"),
        )
