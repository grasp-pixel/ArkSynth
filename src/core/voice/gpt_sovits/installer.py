"""GPT-SoVITS 자동 설치 관리자

GPT-SoVITS Windows 통합 패키지를 다운로드하여 설치합니다.
통합 패키지는 모든 종속성이 포함되어 있어 바로 실행 가능합니다.
"""

import asyncio
import logging
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Awaitable, Callable, Optional, Union
from dataclasses import dataclass

import aiohttp
import py7zr

logger = logging.getLogger(__name__)


@dataclass
class InstallProgress:
    """설치 진행 상황"""
    stage: str  # downloading, extracting, verifying, complete, error
    progress: float  # 0.0 ~ 1.0
    message: str
    error: Optional[str] = None


# 콜백 타입: 동기 또는 비동기 모두 지원
ProgressCallback = Callable[[InstallProgress], Union[None, Awaitable[None]]]


class GPTSoVITSInstaller:
    """GPT-SoVITS 자동 설치 관리자

    GPT-SoVITS Windows 통합 패키지를 다운로드하여 설치합니다.
    - 모든 종속성 포함 (Python, PyTorch, CUDA 등)
    - 바로 실행 가능
    """

    # 기본 설치 경로
    DEFAULT_INSTALL_PATH = Path("tools/gpt_sovits")

    # GPT-SoVITS v2pro Windows 통합 패키지 (7z 형식)
    # Hugging Face에서 호스팅 - 2025.06 최신 버전
    INTEGRATED_PACKAGE_URL = "https://huggingface.co/lj1995/GPT-SoVITS-windows-package/resolve/main/GPT-SoVITS-v2pro-20250604.7z"
    INTEGRATED_FOLDER = "GPT-SoVITS-v2pro-20250604"
    ARCHIVE_FILENAME = "gpt_sovits_package.7z"

    def __init__(self, install_path: Optional[Path] = None):
        self.install_path = install_path or self.DEFAULT_INSTALL_PATH
        self._cancelled = False

    @property
    def python_exe(self) -> Path:
        """Python 실행 파일 경로 (통합 패키지 runtime)"""
        return self.gpt_sovits_path / "runtime" / "python.exe"

    @property
    def gpt_sovits_path(self) -> Path:
        """GPT-SoVITS 경로"""
        return self.install_path / self.INTEGRATED_FOLDER

    @property
    def log_file(self) -> Path:
        """설치 로그 파일"""
        return self.install_path / "install.log"

    def is_installed(self) -> bool:
        """설치 완료 여부 확인"""
        api_script = self.gpt_sovits_path / "api_v2.py"
        if not api_script.exists():
            api_script = self.gpt_sovits_path / "api.py"
        return self.python_exe.exists() and api_script.exists()

    def cancel(self):
        """설치 취소"""
        self._cancelled = True

    async def _emit_progress(self, callback: ProgressCallback, progress: InstallProgress):
        """진행률 콜백 호출 (동기/비동기 모두 지원)"""
        result = callback(progress)
        if asyncio.iscoroutine(result):
            await result

    async def install(
        self,
        on_progress: ProgressCallback,
        cuda_version: str = "cu121"  # 통합 패키지는 CUDA 포함이므로 무시
    ) -> bool:
        """GPT-SoVITS 통합 패키지 설치

        Args:
            on_progress: 진행 상황 콜백 (동기 또는 비동기)
            cuda_version: 무시됨 (통합 패키지는 CUDA 포함)

        Returns:
            설치 성공 여부
        """
        self._cancelled = False

        try:
            # 설치 디렉토리 생성
            self.install_path.mkdir(parents=True, exist_ok=True)

            # 로그 파일 초기화
            with open(self.log_file, "w", encoding="utf-8") as f:
                f.write("GPT-SoVITS 통합 패키지 설치 시작\n")
                f.write(f"설치 경로: {self.install_path.absolute()}\n\n")

            # 이미 설치되어 있으면 스킵
            if self.is_installed():
                self._log("이미 설치되어 있음")
                await self._emit_progress(on_progress, InstallProgress(
                    stage="complete",
                    progress=1.0,
                    message="이미 설치되어 있습니다"
                ))
                return True

            # Stage 1: 다운로드 (0-80%)
            if self._cancelled:
                return False
            await self._download_package(on_progress)

            # Stage 2: 압축 해제 (80-95%)
            if self._cancelled:
                return False
            await self._extract_package(on_progress)

            # Stage 3: 검증 (95-100%)
            if self._cancelled:
                return False
            verify_result = await self._verify_installation(on_progress)

            if verify_result:
                await self._emit_progress(on_progress, InstallProgress(
                    stage="complete",
                    progress=1.0,
                    message="설치 완료!"
                ))
                self._log("설치 완료!")
                return True
            else:
                await self._emit_progress(on_progress, InstallProgress(
                    stage="error",
                    progress=1.0,
                    message="설치 검증 실패",
                    error="Python 또는 API 스크립트를 찾을 수 없습니다"
                ))
                return False

        except asyncio.CancelledError:
            await self._emit_progress(on_progress, InstallProgress(
                stage="error",
                progress=0,
                message="설치 취소됨",
                error="사용자에 의해 취소됨"
            ))
            return False
        except asyncio.TimeoutError:
            error_msg = "다운로드 타임아웃 - 네트워크 연결을 확인하고 다시 시도하세요"
            logger.error("다운로드 타임아웃")
            self._log(f"오류: {error_msg}")
            await self._emit_progress(on_progress, InstallProgress(
                stage="error",
                progress=0,
                message="다운로드 타임아웃",
                error=error_msg
            ))
            return False
        except Exception as e:
            error_msg = str(e) or "알 수 없는 오류"
            logger.exception("설치 중 오류 발생")
            self._log(f"오류: {error_msg}")
            await self._emit_progress(on_progress, InstallProgress(
                stage="error",
                progress=0,
                message="설치 실패",
                error=error_msg
            ))
            return False

    def _log(self, message: str):
        """로그 파일에 기록"""
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(f"{message}\n")
        except Exception:
            pass

    async def _download_package(self, on_progress: ProgressCallback):
        """통합 패키지 다운로드"""
        await self._emit_progress(on_progress, InstallProgress(
            stage="downloading",
            progress=0.0,
            message="GPT-SoVITS 통합 패키지 다운로드 준비 중..."
        ))

        archive_path = self.install_path / self.ARCHIVE_FILENAME

        # 이미 다운로드된 파일이 있으면 스킵 (최소 7.5GB 이상이어야 완료된 것으로 간주)
        min_expected_size = 7_500_000_000  # 7.5GB (v2pro는 약 7.8GB)
        if archive_path.exists():
            file_size = archive_path.stat().st_size
            if file_size >= min_expected_size:
                self._log(f"이미 다운로드된 패키지 발견 ({file_size / (1024**3):.1f}GB), 스킵")
                await self._emit_progress(on_progress, InstallProgress(
                    stage="downloading",
                    progress=0.80,
                    message="이미 다운로드된 패키지 사용"
                ))
                return
            else:
                # 부분 다운로드된 파일 삭제
                self._log(f"부분 다운로드 파일 삭제 ({file_size / (1024**3):.1f}GB)")
                archive_path.unlink()

        self._log(f"다운로드 시작: {self.INTEGRATED_PACKAGE_URL}")

        # 대용량 파일 다운로드를 위한 타임아웃 설정
        # 각 청크 읽기마다 타임아웃이 갱신되도록 sock_read 사용
        timeout = aiohttp.ClientTimeout(
            total=0,        # 전체 타임아웃 비활성화
            connect=60,     # 연결 타임아웃 60초
            sock_read=300,  # 각 청크 읽기 타임아웃 5분 (청크마다 갱신됨)
        )

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(self.INTEGRATED_PACKAGE_URL) as resp:
                    if resp.status != 200:
                        raise Exception(f"다운로드 실패: HTTP {resp.status}")

                    total = int(resp.headers.get('content-length', 0))
                    downloaded = 0

                    with open(archive_path, 'wb') as f:
                        async for chunk in resp.content.iter_chunked(65536):  # 64KB chunks
                            if self._cancelled:
                                raise asyncio.CancelledError()

                            f.write(chunk)
                            downloaded += len(chunk)

                            if total > 0:
                                file_progress = downloaded / total
                                overall_progress = file_progress * 0.80  # 다운로드는 전체의 80%
                                size_mb = downloaded / (1024 * 1024)
                                total_mb = total / (1024 * 1024)
                                await self._emit_progress(on_progress, InstallProgress(
                                    stage="downloading",
                                    progress=overall_progress,
                                    message=f"다운로드 중... ({size_mb:.0f}/{total_mb:.0f} MB)"
                                ))

            self._log(f"다운로드 완료: {archive_path}")
        except Exception as e:
            # 다운로드 실패 시 부분 파일 삭제
            if archive_path.exists():
                try:
                    archive_path.unlink()
                    self._log("다운로드 실패로 부분 파일 삭제")
                except Exception:
                    pass
            raise

    def _find_7z_executable(self) -> Path | None:
        """시스템에 설치된 7z.exe 찾기"""
        # 일반적인 7-Zip 설치 경로
        candidates = [
            Path("C:/Program Files/7-Zip/7z.exe"),
            Path("C:/Program Files (x86)/7-Zip/7z.exe"),
        ]

        # PATH에서도 찾기
        import shutil as sh
        path_7z = sh.which("7z")
        if path_7z:
            candidates.insert(0, Path(path_7z))

        for candidate in candidates:
            if candidate.exists():
                return candidate

        return None

    async def _extract_package(self, on_progress: ProgressCallback):
        """패키지 압축 해제 (7z 형식)"""
        archive_path = self.install_path / self.ARCHIVE_FILENAME

        if not archive_path.exists():
            raise Exception("다운로드된 패키지를 찾을 수 없습니다")

        await self._emit_progress(on_progress, InstallProgress(
            stage="extracting",
            progress=0.80,
            message="압축 해제 중... (~20GB, 수 분 소요)"
        ))

        # 7z.exe 우선 사용 (훨씬 빠름)
        seven_zip = self._find_7z_executable()

        if seven_zip:
            self._log(f"7-Zip 사용: {seven_zip}")
            await self._extract_with_7z(archive_path, seven_zip, on_progress)
        else:
            self._log("7-Zip 미설치, py7zr 사용 (느림)")
            await self._extract_with_py7zr(archive_path, on_progress)

        self._log("압축 해제 완료")

        # 7z 파일 삭제 (공간 절약)
        try:
            archive_path.unlink()
            self._log("7z 파일 삭제 완료")
        except Exception as e:
            self._log(f"7z 파일 삭제 실패: {e}")

        await self._emit_progress(on_progress, InstallProgress(
            stage="extracting",
            progress=0.95,
            message="압축 해제 완료"
        ))

    async def _extract_with_7z(self, archive_path: Path, seven_zip: Path, on_progress: ProgressCallback):
        """7z.exe를 사용한 빠른 압축 해제"""
        self._log("7z.exe로 압축 해제 시작...")

        def extract_sync():
            # 7z x archive.7z -ooutput_dir -y
            # -y: 모든 질문에 Yes
            # -bsp1: 진행률 출력 (stdout)
            result = subprocess.run(
                [
                    str(seven_zip),
                    "x",  # extract with full paths
                    str(archive_path),
                    f"-o{self.install_path}",
                    "-y",  # assume Yes on all queries
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            if result.returncode != 0:
                raise Exception(f"7z 압축 해제 실패: {result.stderr}")

            return result.stdout

        loop = asyncio.get_event_loop()
        output = await loop.run_in_executor(None, extract_sync)
        self._log(f"7z.exe 출력: {output[:500] if output else '(없음)'}")

    async def _extract_with_py7zr(self, archive_path: Path, on_progress: ProgressCallback):
        """py7zr 라이브러리를 사용한 압축 해제 (폴백, 느림)"""
        self._log("py7zr로 압축 해제 시작 (7-Zip이 설치되어 있으면 더 빠릅니다)...")

        await self._emit_progress(on_progress, InstallProgress(
            stage="extracting",
            progress=0.80,
            message="압축 해제 중... (7-Zip 설치 시 더 빠름)"
        ))

        def extract_sync():
            with py7zr.SevenZipFile(archive_path, mode='r') as archive:
                all_files = archive.getnames()
                self._log(f"총 {len(all_files)}개 파일 압축 해제 예정")
                archive.extractall(path=self.install_path)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, extract_sync)

    async def _verify_installation(self, on_progress: ProgressCallback) -> bool:
        """설치 검증"""
        await self._emit_progress(on_progress, InstallProgress(
            stage="verifying",
            progress=0.95,
            message="설치 검증 중..."
        ))

        # 1. Python 실행 파일 확인
        if not self.python_exe.exists():
            self._log(f"검증 실패: {self.python_exe} 없음")
            return False

        # 2. API 스크립트 확인
        api_script = self.gpt_sovits_path / "api_v2.py"
        if not api_script.exists():
            api_script = self.gpt_sovits_path / "api.py"

        if not api_script.exists():
            self._log("검증 실패: api.py/api_v2.py 없음")
            return False

        self._log("설치 검증 통과")
        await self._emit_progress(on_progress, InstallProgress(
            stage="verifying",
            progress=1.0,
            message="검증 완료"
        ))

        return True

    async def get_install_info(self) -> dict:
        """설치 정보 조회"""
        info = {
            "is_installed": self.is_installed(),
            "install_path": str(self.install_path.absolute()),
            "python_path": str(self.python_exe.absolute()) if self.python_exe.exists() else None,
            "gpt_sovits_path": str(self.gpt_sovits_path.absolute()) if self.gpt_sovits_path.exists() else None,
        }

        # 설치되어 있으면 추가 정보
        if info["is_installed"]:
            try:
                result = subprocess.run(
                    [str(self.python_exe), "-c", "import torch; print(torch.__version__)"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    encoding="utf-8",
                    errors="replace"
                )
                if result.returncode == 0:
                    info["torch_version"] = result.stdout.strip()

                result = subprocess.run(
                    [str(self.python_exe), "-c", "import torch; print(torch.cuda.is_available())"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    encoding="utf-8",
                    errors="replace"
                )
                if result.returncode == 0:
                    info["cuda_available"] = result.stdout.strip() == "True"
            except Exception:
                pass

        return info

    def cleanup(self):
        """설치 폴더 정리 (삭제)"""
        if self.install_path.exists():
            try:
                shutil.rmtree(self.install_path)
                logger.info(f"설치 폴더 삭제: {self.install_path}")
            except Exception as e:
                logger.error(f"정리 실패: {e}")


# 전역 인스턴스
_installer: Optional[GPTSoVITSInstaller] = None


def get_installer(install_path: Optional[Path] = None) -> GPTSoVITSInstaller:
    """설치 관리자 인스턴스 가져오기"""
    global _installer
    if _installer is None:
        _installer = GPTSoVITSInstaller(install_path)
    return _installer


def reset_installer():
    """설치 관리자 초기화"""
    global _installer
    _installer = None
