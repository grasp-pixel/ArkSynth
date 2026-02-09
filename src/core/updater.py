"""앱 자동 업데이트 관리자

GitHub Releases에서 최신 버전을 확인하고 제자리 업데이트합니다.
- Python 소스: 바로 교체 (실행 중 잠기지 않음)
- ArkSynth.exe: rename 트릭 (실행 중 rename 가능, 덮어쓰기 불가)
"""

import asyncio
import hashlib
import json
import logging
import os
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable, Optional, Union

import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class UpdateProgress:
    """업데이트 진행 상황"""
    stage: str  # checking, downloading, verifying, backing_up, applying, complete, error
    progress: float  # 0.0 ~ 1.0
    message: str
    error: Optional[str] = None


@dataclass
class UpdateInfo:
    """업데이트 정보"""
    available: bool
    current_version: str
    latest_version: str
    changelog: str = ""
    download_url: str = ""
    filename: str = ""
    size: int = 0
    sha256: str = ""
    minimum_version: str = "0.0.0"


# 콜백 타입: 동기 또는 비동기 모두 지원
ProgressCallback = Callable[[UpdateProgress], Union[None, Awaitable[None]]]


def _compare_versions(v1: str, v2: str) -> int:
    """semver 비교. v1 > v2이면 양수, v1 < v2이면 음수, 같으면 0"""
    parts1 = [int(x) for x in v1.split(".")]
    parts2 = [int(x) for x in v2.split(".")]
    # 3자리로 패딩
    max_len = max(len(parts1), len(parts2), 3)
    parts1 += [0] * (max_len - len(parts1))
    parts2 += [0] * (max_len - len(parts2))
    for a, b in zip(parts1, parts2):
        if a != b:
            return a - b
    return 0


class AppUpdater:
    """ArkSynth 자동 업데이트 관리자"""

    GITHUB_API = "https://api.github.com/repos/{repo}/releases/latest"
    MANIFEST_FILENAME = "update-manifest.json"

    def __init__(self, app_root: Optional[Path] = None, repo: str = "grasp-pixel/ArkSynth"):
        self.app_root = app_root or self._detect_app_root()
        self.repo = repo
        self._cancelled = False

    @staticmethod
    def _detect_app_root() -> Path:
        """배포 구조 자동 감지: app/ 폴더가 있으면 그 안, 아니면 현재 디렉토리"""
        cwd = Path.cwd()
        if (cwd / "app" / "pyproject.toml").exists():
            return cwd / "app"
        return cwd

    def _get_current_version(self) -> str:
        """현재 버전 읽기"""
        version_file = self.app_root / "version.json"
        if version_file.exists():
            try:
                return json.loads(version_file.read_text(encoding="utf-8"))["version"]
            except Exception:
                pass
        return "0.0.0"

    def cancel(self):
        """업데이트 취소"""
        self._cancelled = True

    async def _emit_progress(self, callback: ProgressCallback, progress: UpdateProgress):
        """진행률 콜백 호출 (동기/비동기 모두 지원)"""
        result = callback(progress)
        if asyncio.iscoroutine(result):
            await result

    async def check_update(self) -> UpdateInfo:
        """GitHub에서 최신 릴리즈 확인"""
        current = self._get_current_version()
        api_url = self.GITHUB_API.format(repo=self.repo)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, headers={"Accept": "application/vnd.github.v3+json"}) as resp:
                    if resp.status == 404:
                        return UpdateInfo(available=False, current_version=current, latest_version=current)
                    if resp.status != 200:
                        raise Exception(f"GitHub API 오류: HTTP {resp.status}")

                    release = await resp.json()

                # update-manifest.json 에셋 찾기
                manifest_asset = None
                for asset in release.get("assets", []):
                    if asset["name"] == self.MANIFEST_FILENAME:
                        manifest_asset = asset
                        break

                if manifest_asset is None:
                    # manifest 없으면 릴리즈 태그에서 버전만 비교
                    tag = release.get("tag_name", "").lstrip("v")
                    return UpdateInfo(
                        available=_compare_versions(tag, current) > 0,
                        current_version=current,
                        latest_version=tag,
                        changelog=release.get("body", ""),
                    )

                # manifest 다운로드
                async with session.get(manifest_asset["browser_download_url"]) as resp:
                    if resp.status != 200:
                        raise Exception(f"manifest 다운로드 실패: HTTP {resp.status}")
                    manifest = await resp.json(content_type=None)

                latest = manifest["version"]
                available = _compare_versions(latest, current) > 0

                # update zip 에셋 URL 찾기
                download_url = ""
                update_filename = manifest.get("filename", "")
                for asset in release.get("assets", []):
                    if asset["name"] == update_filename:
                        download_url = asset["browser_download_url"]
                        break

                return UpdateInfo(
                    available=available,
                    current_version=current,
                    latest_version=latest,
                    changelog=manifest.get("changelog", release.get("body", "")),
                    download_url=download_url,
                    filename=update_filename,
                    size=manifest.get("size", 0),
                    sha256=manifest.get("sha256", ""),
                    minimum_version=manifest.get("minimum_version", "0.0.0"),
                )

        except aiohttp.ClientError as e:
            raise Exception(f"네트워크 오류: {e}")

    async def apply_update(self, update_info: UpdateInfo, on_progress: ProgressCallback) -> bool:
        """업데이트 다운로드 및 적용"""
        self._cancelled = False

        if not update_info.download_url:
            await self._emit_progress(on_progress, UpdateProgress(
                stage="error", progress=0, message="다운로드 URL 없음",
                error="update-manifest.json에 다운로드 URL이 없습니다",
            ))
            return False

        temp_dir = self.app_root / "_update_temp"
        archive_path = self.app_root / "_update.zip"

        try:
            # 1. 다운로드 (0~60%)
            await self._download(update_info, archive_path, on_progress)
            if self._cancelled:
                return False

            # 2. SHA256 검증 (60~65%)
            if update_info.sha256:
                await self._verify_hash(archive_path, update_info.sha256, on_progress)
                if self._cancelled:
                    return False

            # 3. 기존 파일 백업 (65~70%)
            await self._backup(on_progress)
            if self._cancelled:
                return False

            # 4. 압축 해제 + 파일 교체 (70~95%)
            await self._extract_and_apply(archive_path, temp_dir, on_progress)
            if self._cancelled:
                return False

            # 5. 완료 (95~100%)
            await self._emit_progress(on_progress, UpdateProgress(
                stage="complete", progress=1.0,
                message=f"v{update_info.latest_version} 업데이트 완료. 재시작이 필요합니다.",
            ))
            return True

        except asyncio.CancelledError:
            await self._rollback()
            await self._emit_progress(on_progress, UpdateProgress(
                stage="error", progress=0, message="업데이트 취소됨", error="사용자에 의해 취소됨",
            ))
            return False
        except Exception as e:
            logger.exception("업데이트 중 오류 발생")
            await self._rollback()
            await self._emit_progress(on_progress, UpdateProgress(
                stage="error", progress=0, message="업데이트 실패",
                error=str(e) or "알 수 없는 오류",
            ))
            return False
        finally:
            # 임시 파일 정리
            if archive_path.exists():
                try:
                    archive_path.unlink()
                except Exception:
                    pass
            if temp_dir.exists():
                try:
                    shutil.rmtree(temp_dir)
                except Exception:
                    pass

    async def _download(self, update_info: UpdateInfo, dest: Path, on_progress: ProgressCallback):
        """업데이트 패키지 다운로드"""
        await self._emit_progress(on_progress, UpdateProgress(
            stage="downloading", progress=0.0, message="다운로드 준비 중...",
        ))

        timeout = aiohttp.ClientTimeout(total=0, connect=60, sock_read=300)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(update_info.download_url) as resp:
                if resp.status != 200:
                    raise Exception(f"다운로드 실패: HTTP {resp.status}")

                total = int(resp.headers.get("content-length", 0)) or update_info.size
                downloaded = 0

                with open(dest, "wb") as f:
                    async for chunk in resp.content.iter_chunked(65536):
                        if self._cancelled:
                            raise asyncio.CancelledError()
                        f.write(chunk)
                        downloaded += len(chunk)

                        if total > 0:
                            file_progress = downloaded / total
                            overall = file_progress * 0.60  # 다운로드는 전체의 60%
                            size_mb = downloaded / (1024 * 1024)
                            total_mb = total / (1024 * 1024)
                            await self._emit_progress(on_progress, UpdateProgress(
                                stage="downloading", progress=overall,
                                message=f"다운로드 중... ({size_mb:.1f}/{total_mb:.1f} MB)",
                            ))

        logger.info("다운로드 완료: %s", dest)

    async def _verify_hash(self, archive: Path, expected_sha256: str, on_progress: ProgressCallback):
        """SHA256 해시 검증"""
        await self._emit_progress(on_progress, UpdateProgress(
            stage="verifying", progress=0.60, message="파일 무결성 검증 중...",
        ))

        def compute_hash():
            h = hashlib.sha256()
            with open(archive, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    h.update(chunk)
            return h.hexdigest()

        loop = asyncio.get_running_loop()
        actual = await loop.run_in_executor(None, compute_hash)

        if actual != expected_sha256:
            raise Exception(f"SHA256 불일치: 예상 {expected_sha256[:16]}..., 실제 {actual[:16]}...")

        await self._emit_progress(on_progress, UpdateProgress(
            stage="verifying", progress=0.65, message="검증 완료",
        ))
        logger.info("SHA256 검증 통과")

    async def _backup(self, on_progress: ProgressCallback):
        """기존 파일 백업"""
        await self._emit_progress(on_progress, UpdateProgress(
            stage="backing_up", progress=0.65, message="기존 파일 백업 중...",
        ))

        def do_backup():
            for dir_name in ["src/core", "src/tools"]:
                src = self.app_root / dir_name
                bak = self.app_root / f"{dir_name}.bak"
                if src.exists():
                    if bak.exists():
                        shutil.rmtree(bak)
                    shutil.copytree(src, bak)

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, do_backup)

        await self._emit_progress(on_progress, UpdateProgress(
            stage="backing_up", progress=0.70, message="백업 완료",
        ))
        logger.info("백업 완료")

    async def _rollback(self):
        """백업에서 복원"""
        logger.info("롤백 시작")

        def do_rollback():
            for dir_name in ["src/core", "src/tools"]:
                bak = self.app_root / f"{dir_name}.bak"
                target = self.app_root / dir_name
                if bak.exists():
                    if target.exists():
                        shutil.rmtree(target)
                    shutil.move(str(bak), str(target))

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, do_rollback)
        logger.info("롤백 완료")

    async def _extract_and_apply(self, archive: Path, temp_dir: Path, on_progress: ProgressCallback):
        """zip 압축 해제 및 파일 교체"""
        await self._emit_progress(on_progress, UpdateProgress(
            stage="applying", progress=0.70, message="업데이트 적용 중...",
        ))

        def do_extract_and_apply():
            # 임시 폴더에 압축 해제
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
            temp_dir.mkdir(parents=True)

            with zipfile.ZipFile(archive, "r") as zf:
                zf.extractall(temp_dir)

            # zip 내부에 app/ 폴더가 있으면 그 안의 내용 사용
            extracted_root = temp_dir
            app_subdir = temp_dir / "app"
            if app_subdir.exists() and app_subdir.is_dir():
                extracted_root = app_subdir

            # Python 소스 교체
            for dir_name in ["src/core", "src/tools"]:
                new_src = extracted_root / dir_name
                if new_src.exists():
                    target = self.app_root / dir_name
                    if target.exists():
                        shutil.rmtree(target)
                    shutil.copytree(new_src, target)

            # ArkSynth.exe: rename 트릭
            new_exe = extracted_root / "ArkSynth.exe"
            if new_exe.exists():
                current_exe = self.app_root / "ArkSynth.exe"
                if current_exe.exists():
                    old_exe = self.app_root / "ArkSynth.exe.old"
                    if old_exe.exists():
                        old_exe.unlink()
                    # 실행 중인 exe를 rename (Windows에서 가능)
                    os.rename(current_exe, old_exe)
                shutil.copy2(new_exe, current_exe)

            # version.json 교체
            new_version = extracted_root / "version.json"
            if new_version.exists():
                shutil.copy2(new_version, self.app_root / "version.json")

            # pyproject.toml, uv.lock 교체
            for fname in ["pyproject.toml", "uv.lock"]:
                new_file = extracted_root / fname
                if new_file.exists():
                    shutil.copy2(new_file, self.app_root / fname)

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, do_extract_and_apply)

        await self._emit_progress(on_progress, UpdateProgress(
            stage="applying", progress=0.95, message="파일 교체 완료",
        ))
        logger.info("파일 교체 완료")


# 전역 인스턴스
_updater: Optional[AppUpdater] = None


def get_updater(repo: Optional[str] = None) -> AppUpdater:
    """업데이터 인스턴스 가져오기"""
    global _updater
    if _updater is None:
        _updater = AppUpdater(repo=repo or "grasp-pixel/ArkSynth")
    return _updater
