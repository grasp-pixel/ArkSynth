"""arkprts 기반 게임 데이터 소스

게임 서버에서 직접 데이터를 다운로드 (arkprts 패키지 사용)
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Awaitable, Callable, Optional, Union

from .gamedata_source import GamedataSource
from .gamedata_updater import UpdateProgress

logger = logging.getLogger(__name__)


class ArkprtsGamedataSource(GamedataSource):
    """arkprts를 사용하여 게임 서버에서 직접 데이터를 다운로드하는 소스"""

    source_type = "arkprts"

    def __init__(self, data_root: str | Path):
        super().__init__(data_root)
        self._process: Optional[asyncio.subprocess.Process] = None
        self._cancel_flag = False

    async def update(
        self,
        server: str = "kr",
        on_progress: Optional[
            Callable[[UpdateProgress], Union[None, Awaitable[None]]]
        ] = None,
    ) -> bool:
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
            await report("checking", 0.0, "arkprts로 데이터 다운로드 준비 중...")

            if self._cancel_flag:
                await report("error", 0.0, "취소됨", "사용자가 취소함")
                return False

            # subprocess로 arkprts.assets 실행
            output_path = str(self.gamedata_path)
            cmd = [
                sys.executable,
                "-m",
                "arkprts.assets",
                output_path,
                "--server",
                server,
            ]

            logger.info(f"arkprts 실행: {' '.join(cmd)}")
            await report("downloading", 0.1, f"{server} 서버 데이터 다운로드 시작...")

            self._process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # stderr 버퍼 (에러 시 메시지 표시용)
            stderr_lines: list[str] = []
            progress_value = 0.1

            async def read_stream(stream, name: str, buffer: list[str] | None = None):
                nonlocal progress_value
                while True:
                    if self._cancel_flag:
                        break

                    try:
                        line = await asyncio.wait_for(
                            stream.readline(), timeout=10.0
                        )
                        if not line:
                            break

                        line_text = line.decode("utf-8", errors="ignore").strip()
                        if not line_text:
                            continue

                        if buffer is not None:
                            buffer.append(line_text)

                        logger.debug(f"[arkprts][{name}] {line_text}")

                        # 진행률 추정 (로그 라인 기반)
                        progress_value = min(0.9, progress_value + 0.003)
                        display_msg = line_text[:120]
                        await report("downloading", progress_value, display_msg)

                    except asyncio.TimeoutError:
                        if self._cancel_flag:
                            break
                        await report("downloading", progress_value, "처리 중...")

            read_tasks = [
                asyncio.create_task(
                    read_stream(self._process.stdout, "stdout")
                ),
                asyncio.create_task(
                    read_stream(self._process.stderr, "stderr", stderr_lines)
                ),
            ]

            # 프로세스 완료 대기
            await self._process.wait()

            # 읽기 태스크 완료 대기 (EOF 도달하면 즉시 종료됨)
            try:
                await asyncio.wait_for(
                    asyncio.gather(*read_tasks, return_exceptions=True),
                    timeout=2.0,
                )
            except asyncio.TimeoutError:
                for task in read_tasks:
                    task.cancel()

            if self._cancel_flag:
                await report("error", 0.0, "취소됨", "사용자가 취소함")
                return False

            if self._process.returncode != 0:
                error_msg = "\n".join(stderr_lines[-5:]) if stderr_lines else ""
                logger.error(f"arkprts 실패 (코드 {self._process.returncode}): {error_msg}")
                await report(
                    "error", 0.0, "다운로드 실패",
                    error_msg[:200] or f"프로세스 종료 코드: {self._process.returncode}",
                )
                return False

            # 업데이트 정보 저장
            self._save_update_info(server)
            await report("complete", 1.0, "업데이트 완료!")
            return True

        except asyncio.CancelledError:
            await report("error", 0.0, "취소됨", "작업이 취소되었습니다")
            return False
        except Exception as e:
            logger.exception(f"arkprts 업데이트 실패: {e}")
            await report("error", 0.0, "업데이트 실패", str(e))
            return False
        finally:
            self._process = None

    def cancel(self):
        self._cancel_flag = True
        if self._process and self._process.returncode is None:
            try:
                self._process.kill()
            except ProcessLookupError:
                pass
