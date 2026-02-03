"""게임 데이터 업데이터

arkprts 라이브러리를 사용하여 Arknights 게임 데이터를 다운로드/업데이트
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Awaitable, Callable, Optional, Union

logger = logging.getLogger(__name__)


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

    arkprts를 사용하여 게임 서버에서 직접 데이터를 다운로드합니다.
    """

    def __init__(self, data_root: str | Path):
        """
        Args:
            data_root: data 폴더 경로
        """
        self.data_root = Path(data_root)
        self.gamedata_path = self.data_root / "gamedata"
        self._cancel_flag = False
        self._update_info_path = self.gamedata_path / ".update_info.json"

    def get_status(self, server: str = "kr") -> GamedataStatus:
        """현재 게임 데이터 상태 확인"""
        server_path = self.gamedata_path / server
        story_path = server_path / "gamedata" / "story"

        exists = story_path.exists()
        story_count = 0
        last_updated = None

        if exists:
            # 스토리 파일 수 카운트
            story_count = sum(1 for _ in story_path.rglob("*.txt"))

        # 업데이트 정보 읽기
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
        on_progress: Optional[Callable[[UpdateProgress], Union[None, Awaitable[None]]]] = None,
    ) -> bool:
        """게임 데이터 업데이트

        Args:
            server: 서버 코드 (kr, en, jp, cn, tw)
            on_progress: 진행률 콜백 (동기 또는 비동기 함수)

        Returns:
            성공 여부
        """
        self._cancel_flag = False

        async def report(stage: str, progress: float, message: str, error: str = None):
            logger.info(f"[GamedataUpdater] report: stage={stage}, progress={progress}, message={message}, error={error}")
            if on_progress:
                try:
                    progress_obj = UpdateProgress(stage, progress, message, error)
                    logger.debug(f"[GamedataUpdater] Calling on_progress with: {progress_obj}")
                    result = on_progress(progress_obj)
                    # 코루틴이면 await
                    if asyncio.iscoroutine(result):
                        logger.debug("[GamedataUpdater] on_progress returned coroutine, awaiting...")
                        await result
                    logger.debug("[GamedataUpdater] on_progress completed")
                except Exception as e:
                    logger.exception(f"[GamedataUpdater] Error in on_progress callback: {e}")

        try:
            # arkprts 임포트 확인
            await report("checking", 0.0, "arkprts 라이브러리 확인 중...")

            try:
                import arkprts
            except ImportError:
                await report(
                    "error",
                    0.0,
                    "arkprts가 설치되지 않았습니다",
                    "pip install arkprts[all] 명령으로 설치해주세요",
                )
                return False

            if self._cancel_flag:
                await report("error", 0.0, "취소됨", "사용자가 취소함")
                return False

            # 다운로드 시작
            await report("downloading", 0.1, f"{server} 서버 데이터 다운로드 시작...")

            # arkprts.assets 모듈로 다운로드
            # 실제로는 subprocess로 실행하는 것이 더 안정적
            import subprocess
            import sys

            # 출력 경로
            output_path = str(self.gamedata_path)

            # arkprts.assets 명령 실행
            cmd = [
                sys.executable,
                "-m",
                "arkprts.assets",
                output_path,
                "--server",
                server,
                "--log-level",
                "DEBUG",  # DEBUG 레벨로 더 많은 출력 얻기
            ]

            logger.info(f"[GamedataUpdater] Running command: {' '.join(cmd)}")
            logger.info(f"[GamedataUpdater] Python executable: {sys.executable}")
            logger.info(f"[GamedataUpdater] Output path: {output_path}")
            await report("downloading", 0.2, f"arkprts 실행 중... (서버: {server})")

            # 비동기로 subprocess 실행
            logger.info("[GamedataUpdater] Creating subprocess...")
            try:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                logger.info(f"[GamedataUpdater] Subprocess created with PID: {process.pid}")
            except Exception as e:
                logger.exception(f"[GamedataUpdater] Failed to create subprocess: {e}")
                raise

            # stdout과 stderr를 동시에 읽는 태스크
            progress_value = 0.2
            line_count = 0
            last_report_time = asyncio.get_event_loop().time()
            process_finished = False

            async def read_stream(stream, name):
                nonlocal progress_value, line_count, last_report_time, process_finished
                while not process_finished:
                    try:
                        line = await asyncio.wait_for(
                            stream.readline(),
                            timeout=10.0,  # 10초 타임아웃
                        )
                        if not line:
                            break

                        line_count += 1
                        line_text = line.decode("utf-8", errors="ignore").strip()
                        if line_text:
                            logger.info(f"[GamedataUpdater] [{name}][{line_count}] {line_text}")

                            # 진행률 추정 (로그 라인 수 기반)
                            progress_value = min(0.9, progress_value + 0.005)
                            await report("downloading", progress_value, line_text[:100])
                            last_report_time = asyncio.get_event_loop().time()

                    except asyncio.TimeoutError:
                        # 타임아웃 시 하트비트 전송
                        current_time = asyncio.get_event_loop().time()
                        if current_time - last_report_time > 5.0:
                            await report("downloading", progress_value, "처리 중...")
                            last_report_time = current_time

                    if self._cancel_flag:
                        break

            logger.info("[GamedataUpdater] Starting to read process output...")

            # stdout과 stderr 동시 읽기
            try:
                read_tasks = [
                    asyncio.create_task(read_stream(process.stdout, "stdout")),
                    asyncio.create_task(read_stream(process.stderr, "stderr")),
                ]

                # 프로세스 완료 대기
                await process.wait()
                process_finished = True
                logger.info(f"[GamedataUpdater] Process completed with return code: {process.returncode}")

                # 읽기 태스크 완료 대기 (짧은 타임아웃)
                await asyncio.wait_for(asyncio.gather(*read_tasks, return_exceptions=True), timeout=5.0)

            except asyncio.TimeoutError:
                logger.warning("[GamedataUpdater] Timeout waiting for read tasks")
                for task in read_tasks:
                    task.cancel()

            if self._cancel_flag:
                logger.info("[GamedataUpdater] Cancel flag detected, killing process")
                process.kill()
                await report("error", progress_value, "취소됨", "사용자가 취소함")
                return False

            logger.info(f"[GamedataUpdater] Total lines read: {line_count}")

            if process.returncode != 0:
                stderr = await process.stderr.read()
                error_msg = stderr.decode("utf-8", errors="ignore")
                logger.error(f"[GamedataUpdater] Process failed with error: {error_msg}")
                await report("error", progress_value, "다운로드 실패", error_msg[:200])
                return False

            # 업데이트 정보 저장
            logger.info("[GamedataUpdater] Saving update info...")
            self._save_update_info(server)

            logger.info("[GamedataUpdater] Update completed successfully!")
            await report("complete", 1.0, "업데이트 완료!")
            return True

        except asyncio.TimeoutError as e:
            logger.error(f"[GamedataUpdater] Timeout error: {e}")
            await report("error", 0.0, "타임아웃", "다운로드가 너무 오래 걸립니다")
            return False
        except Exception as e:
            logger.exception(f"[GamedataUpdater] Update failed with exception: {e}")
            await report("error", 0.0, "업데이트 실패", str(e))
            return False

    def cancel(self):
        """업데이트 취소"""
        self._cancel_flag = True

    def _save_update_info(self, server: str):
        """업데이트 정보 저장"""
        self.gamedata_path.mkdir(parents=True, exist_ok=True)

        info = {
            "server": server,
            "last_updated": datetime.now().isoformat(),
        }

        with open(self._update_info_path, "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=2)
