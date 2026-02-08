"""게임 데이터 소스 인터페이스

어댑터 패턴으로 다양한 데이터 소스(GitHub, arkprts 등)를 통일된 인터페이스로 제공
"""

import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Awaitable, Callable, Optional, Union

from .gamedata_updater import GamedataStatus, UpdateProgress

logger = logging.getLogger(__name__)


class GamedataSource(ABC):
    """게임 데이터 소스 추상 인터페이스"""

    def __init__(self, data_root: str | Path):
        self.data_root = Path(data_root)
        self.gamedata_path = self.data_root / "gamedata"
        self._update_info_path = self.gamedata_path / ".update_info.json"

    source_type: str  # 소스 식별자 (github, arkprts) — 서브클래스에서 클래스 변수로 정의

    def get_status(self, server: str = "kr") -> GamedataStatus:
        """현재 게임 데이터 상태 확인 — 출력 디렉토리가 동일하므로 공통 구현"""
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

    @abstractmethod
    async def update(
        self,
        server: str = "kr",
        on_progress: Optional[
            Callable[[UpdateProgress], Union[None, Awaitable[None]]]
        ] = None,
    ) -> bool:
        """게임 데이터 다운로드/업데이트"""
        ...

    @abstractmethod
    def cancel(self):
        """진행 중인 업데이트 취소"""
        ...

    def _save_update_info(self, server: str):
        """업데이트 메타 정보 저장"""
        self.gamedata_path.mkdir(parents=True, exist_ok=True)

        info = {
            "server": server,
            "source": self.source_type,
            "last_updated": datetime.now().isoformat(),
        }

        with open(self._update_info_path, "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=2)
