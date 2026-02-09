"""설정 관련 라우터"""

import logging
import asyncio
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..config import config

router = APIRouter()

# 설치 작업 상태 (GPT-SoVITS)
_install_task: Optional[asyncio.Task] = None
_install_progress_queue: Optional[asyncio.Queue] = None

# FFmpeg 설치 작업 상태
_ffmpeg_install_task: Optional[asyncio.Task] = None
_ffmpeg_install_queue: Optional[asyncio.Queue] = None


class DependencyStatus(BaseModel):
    """의존성 상태"""
    name: str
    installed: bool
    version: Optional[str] = None
    path: Optional[str] = None


class SettingsResponse(BaseModel):
    """설정 응답"""
    # 경로 설정
    gpt_sovits_path: str
    models_path: str
    extracted_path: str
    gamedata_path: str

    # 언어 설정
    display_language: str
    voice_language_short: str
    game_language: str
    voice_language: str
    gpt_sovits_language: str

    # TTS 설정
    default_tts_engine: str

    # Whisper 전처리 설정
    whisper_model_size: str
    whisper_compute_type: str
    use_whisper_preprocessing: bool

    # 의존성 상태
    dependencies: list[DependencyStatus]


class UpdateSettingsRequest(BaseModel):
    """설정 업데이트 요청"""
    gpt_sovits_path: Optional[str] = None
    gpt_sovits_language: Optional[str] = None


def check_ffmpeg() -> DependencyStatus:
    """FFmpeg 설치 확인"""
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            # 버전 추출 (첫 줄에서)
            first_line = result.stdout.split("\n")[0]
            version = first_line.split(" ")[2] if len(first_line.split(" ")) > 2 else "unknown"
            path = shutil.which("ffmpeg")
            return DependencyStatus(
                name="FFmpeg",
                installed=True,
                version=version,
                path=path,
            )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return DependencyStatus(name="FFmpeg", installed=False)


def check_ffprobe() -> DependencyStatus:
    """FFprobe 설치 확인"""
    try:
        result = subprocess.run(
            ["ffprobe", "-version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            first_line = result.stdout.split("\n")[0]
            version = first_line.split(" ")[2] if len(first_line.split(" ")) > 2 else "unknown"
            path = shutil.which("ffprobe")
            return DependencyStatus(
                name="FFprobe",
                installed=True,
                version=version,
                path=path,
            )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return DependencyStatus(name="FFprobe", installed=False)


def check_gpt_sovits() -> DependencyStatus:
    """GPT-SoVITS 설치 확인"""
    from ...voice.gpt_sovits import GPTSoVITSConfig

    gpt_config = GPTSoVITSConfig()
    if gpt_config.is_gpt_sovits_installed:
        return DependencyStatus(
            name="GPT-SoVITS",
            installed=True,
            path=str(gpt_config.gpt_sovits_path),
        )

    return DependencyStatus(name="GPT-SoVITS", installed=False)


def check_7zip() -> DependencyStatus:
    """7-Zip 설치 확인"""
    # 일반적인 7-Zip 설치 경로
    candidates = [
        Path("C:/Program Files/7-Zip/7z.exe"),
        Path("C:/Program Files (x86)/7-Zip/7z.exe"),
    ]

    # PATH에서도 찾기
    path_7z = shutil.which("7z")
    if path_7z:
        candidates.insert(0, Path(path_7z))

    for candidate in candidates:
        if candidate.exists():
            # 버전 확인
            try:
                result = subprocess.run(
                    [str(candidate)],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                # 7-Zip 출력에서 버전 추출
                version = "unknown"
                for line in result.stdout.split("\n"):
                    if "7-Zip" in line:
                        parts = line.split()
                        for i, p in enumerate(parts):
                            if p == "7-Zip" and i + 1 < len(parts):
                                version = parts[i + 1]
                                break
                        break

                return DependencyStatus(
                    name="7-Zip",
                    installed=True,
                    version=version,
                    path=str(candidate),
                )
            except Exception:
                return DependencyStatus(
                    name="7-Zip",
                    installed=True,
                    path=str(candidate),
                )

    return DependencyStatus(name="7-Zip", installed=False)



@router.get("", response_model=SettingsResponse)
async def get_settings():
    """현재 설정 조회"""
    from ...voice.gpt_sovits import GPTSoVITSConfig

    gpt_config = GPTSoVITSConfig()

    # 의존성 확인
    dependencies = [
        check_ffmpeg(),
        check_ffprobe(),
        check_7zip(),
        check_gpt_sovits(),
    ]

    return SettingsResponse(
        gpt_sovits_path=str(gpt_config.gpt_sovits_path),
        models_path=str(config.models_path),
        extracted_path=str(config.extracted_path),
        gamedata_path=str(config.gamedata_path),
        display_language=config.display_language,
        voice_language_short=config.voice_language_short,
        game_language=config.game_language,
        voice_language=config.voice_language,
        gpt_sovits_language=config.gpt_sovits_language,
        default_tts_engine=config.default_tts_engine,
        whisper_model_size=gpt_config.whisper_model_size,
        whisper_compute_type=gpt_config.whisper_compute_type,
        use_whisper_preprocessing=gpt_config.use_whisper_preprocessing,
        dependencies=dependencies,
    )


# ============================================================================
# 언어 설정 엔드포인트
# ============================================================================


class LanguageSettingsRequest(BaseModel):
    """언어 설정 변경 요청"""
    display_language: Optional[str] = None  # "ko_KR", "ja_JP", "en_US"
    voice_language: Optional[str] = None    # "ko", "ja", "en"


class LanguageSettingsResponse(BaseModel):
    """언어 설정 응답"""
    display_language: str
    game_language: str            # 서버 코드 (kr, jp, en)
    voice_language: str           # 단축 코드
    voice_folder: str             # 음성 폴더명
    gpt_sovits_language: str
    available_display_languages: list[dict]  # [{short, locale, label, available}]
    available_voice_languages: list[dict]    # [{short, label, available}]


def _check_available_languages() -> tuple[list[dict], list[dict]]:
    """가용 표시/음성 언어 목록 생성"""
    from ...common.language_codes import (
        SUPPORTED_LANGUAGES, LOCALE_TO_SERVER, SHORT_TO_VOICE_FOLDER,
    )

    display_langs = []
    for lang in SUPPORTED_LANGUAGES:
        server = LOCALE_TO_SERVER.get(lang["locale"], "")
        gamedata_dir = config.gamedata_path / server / "gamedata"
        display_langs.append({
            "short": lang["short"],
            "locale": lang["locale"],
            "label": lang["native"],
            "available": gamedata_dir.exists(),
        })

    voice_langs = []
    for lang in SUPPORTED_LANGUAGES:
        voice_folder = SHORT_TO_VOICE_FOLDER.get(lang["short"], "")
        voice_dir = config.extracted_path / voice_folder
        voice_langs.append({
            "short": lang["short"],
            "label": lang["native"],
            "available": voice_dir.exists() and any(voice_dir.iterdir()) if voice_dir.exists() else False,
        })

    return display_langs, voice_langs


@router.get("/language", response_model=LanguageSettingsResponse)
async def get_language_settings():
    """현재 언어 설정 조회"""
    display_langs, voice_langs = _check_available_languages()

    return LanguageSettingsResponse(
        display_language=config.display_language,
        game_language=config.game_language,
        voice_language=config.voice_language_short,
        voice_folder=config.voice_language,
        gpt_sovits_language=config.gpt_sovits_language,
        available_display_languages=display_langs,
        available_voice_languages=voice_langs,
    )


@router.put("/language", response_model=LanguageSettingsResponse)
async def update_language_settings(request: LanguageSettingsRequest):
    """언어 설정 변경"""
    from ..shared_loaders import reset_all

    if request.display_language is not None:
        config.apply_display_language(request.display_language)
        # 표시 언어 변경 → 스토리/캐릭터 데이터 캐시 리셋
        reset_all()

    if request.voice_language is not None:
        config.apply_voice_language(request.voice_language)
        # 음성 언어 변경 → 음성 매퍼/TTS/학습/렌더 캐시 전체 리셋
        reset_all()

    display_langs, voice_langs = _check_available_languages()

    return LanguageSettingsResponse(
        display_language=config.display_language,
        game_language=config.game_language,
        voice_language=config.voice_language_short,
        voice_folder=config.voice_language,
        gpt_sovits_language=config.gpt_sovits_language,
        available_display_languages=display_langs,
        available_voice_languages=voice_langs,
    )


@router.get("/dependencies")
async def check_dependencies():
    """의존성 상태만 확인"""
    return {
        "dependencies": [
            check_ffmpeg(),
            check_ffprobe(),
            check_7zip(),
            check_gpt_sovits(),
        ]
    }


@router.post("/refresh-dependencies")
async def refresh_dependencies():
    """의존성 재검사 + GPT-SoVITS 재초기화"""
    deps = [
        check_ffmpeg(),
        check_ffprobe(),
        check_7zip(),
        check_gpt_sovits(),
    ]
    return {"dependencies": deps}


@router.post("/refresh-all")
async def refresh_all():
    """전체 새로고침: shared_loaders 리셋 + 의존성 재검사 + GPT-SoVITS 재초기화"""
    from ..shared_loaders import reset_all
    reset_all()

    deps = [
        check_ffmpeg(),
        check_ffprobe(),
        check_7zip(),
        check_gpt_sovits(),
    ]
    return {"dependencies": deps, "message": "전체 새로고침 완료"}


@router.post("/shutdown")
async def shutdown():
    """백엔드 서버 종료"""
    import os
    import signal

    logger.info("종료 요청 수신, 서버를 종료합니다...")

    async def _shutdown():
        await asyncio.sleep(0.5)  # 응답 전송 완료 대기
        os.kill(os.getpid(), signal.SIGTERM)

    asyncio.create_task(_shutdown())
    return {"status": "shutting_down", "message": "서버를 종료합니다"}


def _open_in_explorer(folder: Path):
    """탐색기에서 폴더 열기"""
    if sys.platform == "win32":
        subprocess.Popen(["explorer", str(folder)])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(folder)])
    else:
        subprocess.Popen(["xdg-open", str(folder)])


@router.post("/open-folder")
async def open_folder(path: str):
    """폴더 열기 (탐색기)"""
    folder = Path(path)
    if not folder.exists():
        raise HTTPException(status_code=404, detail=f"폴더가 존재하지 않습니다: {path}")

    try:
        _open_in_explorer(folder)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/create-folder")
async def create_folder(path: str):
    """폴더 생성 후 탐색기에서 열기"""
    folder = Path(path)
    try:
        folder.mkdir(parents=True, exist_ok=True)
        _open_in_explorer(folder)
        return {"status": "created", "path": str(folder.absolute())}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ffmpeg/install-guide")
async def ffmpeg_install_guide():
    """FFmpeg 설치 가이드"""
    return {
        "windows": {
            "method": "winget",
            "command": "winget install FFmpeg",
            "alternative": "https://ffmpeg.org/download.html 에서 다운로드 후 PATH에 추가",
        },
        "manual_steps": [
            "1. https://github.com/BtbN/FFmpeg-Builds/releases 에서 다운로드",
            "2. ffmpeg-master-latest-win64-gpl.zip 선택",
            "3. 압축 해제 후 bin 폴더를 PATH 환경변수에 추가",
            "4. 터미널 재시작 후 'ffmpeg -version' 으로 확인",
        ],
    }


@router.post("/ffmpeg/install")
async def start_ffmpeg_install():
    """FFmpeg winget 자동 설치"""
    global _ffmpeg_install_task, _ffmpeg_install_queue

    if _ffmpeg_install_task and not _ffmpeg_install_task.done():
        raise HTTPException(status_code=409, detail="이미 FFmpeg 설치가 진행 중입니다")

    # winget 사용 가능 여부 확인
    try:
        subprocess.run(["winget", "--version"], capture_output=True, timeout=5)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        raise HTTPException(status_code=400, detail="winget이 설치되어 있지 않습니다. 수동 설치를 진행해주세요.")

    _ffmpeg_install_queue = asyncio.Queue()

    async def install_ffmpeg():
        try:
            await _ffmpeg_install_queue.put({
                "stage": "installing", "progress": 10, "message": "winget install 실행 중..."
            })

            process = await asyncio.create_subprocess_exec(
                "winget", "install", "Gyan.FFmpeg",
                "--accept-package-agreements", "--accept-source-agreements",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            await _ffmpeg_install_queue.put({
                "stage": "installing", "progress": 30, "message": "FFmpeg 다운로드 및 설치 중..."
            })

            stdout, stderr = await process.communicate()
            output = (stdout or b"").decode("utf-8", errors="replace")
            err_output = (stderr or b"").decode("utf-8", errors="replace")

            if process.returncode == 0:
                await _ffmpeg_install_queue.put({
                    "stage": "complete", "progress": 100, "message": "FFmpeg 설치 완료"
                })
            elif "already installed" in output.lower() or "이미 설치" in output:
                await _ffmpeg_install_queue.put({
                    "stage": "complete", "progress": 100, "message": "FFmpeg이 이미 설치되어 있습니다"
                })
            else:
                error_msg = err_output.strip() or output.strip() or "알 수 없는 오류"
                await _ffmpeg_install_queue.put({
                    "stage": "error", "progress": 0, "message": "FFmpeg 설치 실패", "error": error_msg
                })
        except Exception as e:
            await _ffmpeg_install_queue.put({
                "stage": "error", "progress": 0, "message": "FFmpeg 설치 실패", "error": str(e)
            })

    _ffmpeg_install_task = asyncio.create_task(install_ffmpeg())
    return {"status": "started", "message": "FFmpeg 설치가 시작되었습니다"}


@router.get("/ffmpeg/install/stream")
async def stream_ffmpeg_install():
    """FFmpeg 설치 진행률 SSE 스트림"""
    global _ffmpeg_install_queue

    if _ffmpeg_install_queue is None:
        raise HTTPException(status_code=404, detail="진행 중인 FFmpeg 설치가 없습니다")

    async def event_generator():
        try:
            while True:
                try:
                    progress = await asyncio.wait_for(
                        _ffmpeg_install_queue.get(), timeout=30.0
                    )
                    yield f"event: progress\ndata: {json.dumps(progress, ensure_ascii=False)}\n\n"

                    if progress.get("stage") in ("complete", "error"):
                        if progress.get("stage") == "complete":
                            yield f"event: complete\ndata: {json.dumps({'success': True})}\n\n"
                        else:
                            yield f"event: error\ndata: {json.dumps({'error': progress.get('error', '')})}\n\n"
                        break
                except asyncio.TimeoutError:
                    yield f"event: ping\ndata: {json.dumps({'status': 'alive'})}\n\n"
        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.get("/7zip/install-guide")
async def sevenzip_install_guide():
    """7-Zip 설치 가이드"""
    return {
        "windows": {
            "method": "winget",
            "command": "winget install 7zip.7zip",
            "alternative": "https://7-zip.org 에서 다운로드",
        },
        "manual_steps": [
            "1. https://7-zip.org/download.html 에서 다운로드",
            "2. 7z2409-x64.exe (64비트) 설치 파일 선택",
            "3. 설치 프로그램 실행 후 기본 설정으로 설치",
            "4. 설치 완료 후 GPT-SoVITS 설치 시 자동 인식됨",
        ],
        "note": "7-Zip은 GPT-SoVITS 압축 해제 속도를 크게 향상시킵니다 (권장)",
    }



# ============================================================================
# GPT-SoVITS 설치 관련 엔드포인트
# ============================================================================


class InstallRequest(BaseModel):
    """설치 요청"""
    cuda_version: str = "cu121"  # cu121, cu124, cpu


class InstallInfoResponse(BaseModel):
    """설치 정보 응답"""
    is_installed: bool
    install_path: Optional[str] = None
    python_path: Optional[str] = None
    gpt_sovits_path: Optional[str] = None
    torch_version: Optional[str] = None
    cuda_available: Optional[bool] = None


@router.get("/gpt-sovits/install-info", response_model=InstallInfoResponse)
async def get_gpt_sovits_install_info():
    """GPT-SoVITS 설치 정보 조회"""
    from ...voice.gpt_sovits.installer import get_installer

    installer = get_installer()
    info = await installer.get_install_info()

    return InstallInfoResponse(**info)


@router.post("/gpt-sovits/install")
async def start_gpt_sovits_install(request: InstallRequest):
    """GPT-SoVITS 설치 시작"""
    global _install_task, _install_progress_queue

    # 이미 설치 중인지 확인
    if _install_task and not _install_task.done():
        raise HTTPException(status_code=409, detail="이미 설치가 진행 중입니다")

    from ...voice.gpt_sovits.installer import get_installer, reset_installer

    # 새 설치 시작
    reset_installer()
    installer = get_installer()

    # 진행률 큐 생성
    _install_progress_queue = asyncio.Queue()

    async def progress_callback(progress):
        if _install_progress_queue:
            await _install_progress_queue.put(progress)

    # 설치 작업 시작
    async def install_task():
        try:
            result = await installer.install(
                on_progress=progress_callback,
                cuda_version=request.cuda_version
            )
            return result
        except Exception as e:
            from ...voice.gpt_sovits.installer import InstallProgress
            await progress_callback(InstallProgress(
                stage="error",
                progress=0,
                message="설치 실패",
                error=str(e)
            ))
            return False

    _install_task = asyncio.create_task(install_task())

    return {"status": "started", "message": "설치가 시작되었습니다"}


@router.get("/gpt-sovits/install/stream")
async def stream_gpt_sovits_install():
    """GPT-SoVITS 설치 진행률 SSE 스트림"""
    global _install_progress_queue

    if _install_progress_queue is None:
        raise HTTPException(status_code=404, detail="진행 중인 설치가 없습니다")

    async def event_generator():
        try:
            while True:
                try:
                    # 큐에서 진행률 가져오기 (타임아웃 30초)
                    progress = await asyncio.wait_for(
                        _install_progress_queue.get(),
                        timeout=30.0
                    )

                    # 진행률 전송
                    data = {
                        "stage": progress.stage,
                        "progress": progress.progress,
                        "message": progress.message,
                        "error": progress.error
                    }
                    yield f"event: progress\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

                    # 완료 또는 에러 시 종료
                    if progress.stage in ("complete", "error"):
                        if progress.stage == "complete":
                            yield f"event: complete\ndata: {json.dumps({'success': True})}\n\n"
                        else:
                            yield f"event: error\ndata: {json.dumps({'error': progress.error})}\n\n"
                        break

                except asyncio.TimeoutError:
                    # keep-alive
                    yield f"event: ping\ndata: {json.dumps({'status': 'alive'})}\n\n"

        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.post("/gpt-sovits/install/cancel")
async def cancel_gpt_sovits_install():
    """GPT-SoVITS 설치 취소"""
    global _install_task

    if _install_task is None or _install_task.done():
        raise HTTPException(status_code=404, detail="진행 중인 설치가 없습니다")

    from ...voice.gpt_sovits.installer import get_installer

    installer = get_installer()
    installer.cancel()

    # 작업 취소
    _install_task.cancel()

    return {"status": "cancelled", "message": "설치가 취소되었습니다"}


@router.get("/gpt-sovits/verify")
async def verify_gpt_sovits_install():
    """GPT-SoVITS 설치 검증"""
    from ...voice.gpt_sovits.installer import get_installer

    installer = get_installer()

    details = {
        "python_exists": installer.python_exe.exists(),
        "gpt_sovits_exists": installer.gpt_sovits_path.exists(),
        "api_script_exists": (
            (installer.gpt_sovits_path / "api_v2.py").exists() or
            (installer.gpt_sovits_path / "api.py").exists()
        ),
    }

    # torch 테스트
    if installer.python_exe.exists():
        try:
            result = subprocess.run(
                [str(installer.python_exe), "-c", "import torch; print(torch.cuda.is_available())"],
                capture_output=True,
                text=True,
                timeout=30
            )
            details["torch_works"] = result.returncode == 0
            details["cuda_available"] = result.stdout.strip() == "True"
        except Exception:
            details["torch_works"] = False
            details["cuda_available"] = False

    valid = all([
        details.get("python_exists", False),
        details.get("api_script_exists", False),
        details.get("torch_works", False),
    ])

    return {"valid": valid, "details": details}


@router.post("/gpt-sovits/cleanup")
async def cleanup_gpt_sovits_install():
    """GPT-SoVITS 설치 폴더 정리 (삭제)"""
    from ...voice.gpt_sovits.installer import get_installer, reset_installer

    installer = get_installer()

    if not installer.install_path.exists():
        return {"status": "ok", "message": "삭제할 폴더가 없습니다"}

    try:
        installer.cleanup()
        reset_installer()
        return {"status": "ok", "message": "설치 폴더가 삭제되었습니다"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"삭제 실패: {e}")


# ============================================================================
# 음성 추출 관련 엔드포인트
# ============================================================================

# 추출 작업 상태
_extract_task: Optional[asyncio.Task] = None
_extract_progress_queue: Optional[asyncio.Queue] = None
_extract_cancel_flag = False


class ExtractRequest(BaseModel):
    """추출 요청"""
    languages: list[str] = ["voice", "voice_kr"]  # 기본: 일본어, 한국어


class ExtractProgress(BaseModel):
    """추출 진행 상태"""
    stage: str  # scanning, extracting, complete, error
    current_lang: Optional[str] = None
    current_file: Optional[str] = None
    processed: int = 0
    total: int = 0
    extracted: int = 0
    message: str = ""
    error: Optional[str] = None


@router.get("/extract/status")
async def get_extract_status():
    """추출 작업 상태 확인"""
    global _extract_task

    if _extract_task is None:
        return {"status": "idle", "message": "대기 중"}

    if _extract_task.done():
        try:
            result = _extract_task.result()
            return {"status": "complete", "result": result}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    return {"status": "running", "message": "추출 진행 중"}


@router.post("/extract/start")
async def start_voice_extraction(request: ExtractRequest):
    """음성 추출 시작"""
    global _extract_task, _extract_progress_queue, _extract_cancel_flag

    # 이미 추출 중인지 확인
    if _extract_task and not _extract_task.done():
        raise HTTPException(status_code=409, detail="이미 추출이 진행 중입니다")

    # Assets/Voice 경로 확인
    voice_assets_dir = Path("Assets/Voice")
    if not voice_assets_dir.exists():
        raise HTTPException(
            status_code=404,
            detail="Assets/Voice 폴더가 없습니다. 게임 리소스를 먼저 복사해주세요."
        )

    # 진행률 큐 생성
    _extract_progress_queue = asyncio.Queue()
    _extract_cancel_flag = False

    async def extract_task():
        from src.tools.extractor.core import extract_audio_from_bundle
        from ...common.language_codes import normalize_voice_folder

        all_stats = {}
        total_extracted = 0

        try:
            for lang in request.languages:
                if _extract_cancel_flag:
                    break

                lang_source = voice_assets_dir / lang
                if not lang_source.exists():
                    continue

                # voice_jp/voice_ja → voice (일본어 정규화)
                output_folder = normalize_voice_folder(lang)
                lang_output = config.extracted_path / output_folder

                # 스캔 단계
                await _extract_progress_queue.put(ExtractProgress(
                    stage="scanning",
                    current_lang=lang,
                    message=f"{lang} 폴더 스캔 중..."
                ))

                ab_files = list(lang_source.glob("*.ab"))
                total = len(ab_files)
                stats = {"processed": 0, "extracted": 0, "failed": 0}

                for i, ab_path in enumerate(ab_files, 1):
                    if _extract_cancel_flag:
                        break

                    # 진행률 전송
                    await _extract_progress_queue.put(ExtractProgress(
                        stage="extracting",
                        current_lang=lang,
                        current_file=ab_path.name,
                        processed=i,
                        total=total,
                        extracted=stats["extracted"],
                        message=f"[{lang}] {ab_path.name} 처리 중..."
                    ))

                    try:
                        # 동기 함수를 별도 스레드에서 실행
                        extracted = await asyncio.get_event_loop().run_in_executor(
                            None,
                            extract_audio_from_bundle,
                            ab_path,
                            lang_output,
                            "mp3"
                        )
                        stats["processed"] += 1
                        stats["extracted"] += len(extracted)
                    except Exception as e:
                        stats["failed"] += 1

                all_stats[lang] = stats
                total_extracted += stats["extracted"]

            # 완료
            await _extract_progress_queue.put(ExtractProgress(
                stage="complete",
                extracted=total_extracted,
                message=f"추출 완료: {total_extracted}개 파일"
            ))

            return all_stats

        except Exception as e:
            logger.error("음성 추출 실패: %s", e, exc_info=True)
            await _extract_progress_queue.put(ExtractProgress(
                stage="error",
                error=str(e),
                message="추출 실패"
            ))
            raise

    _extract_task = asyncio.create_task(extract_task())

    return {"status": "started", "message": "추출이 시작되었습니다", "languages": request.languages}


@router.get("/extract/stream")
async def stream_extract_progress():
    """추출 진행률 SSE 스트림"""
    global _extract_progress_queue

    if _extract_progress_queue is None:
        raise HTTPException(status_code=404, detail="진행 중인 추출이 없습니다")

    async def event_generator():
        try:
            while True:
                try:
                    progress = await asyncio.wait_for(
                        _extract_progress_queue.get(),
                        timeout=30.0
                    )

                    data = progress.model_dump() if hasattr(progress, 'model_dump') else progress.__dict__
                    yield f"event: progress\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

                    if progress.stage in ("complete", "error"):
                        if progress.stage == "complete":
                            yield f"event: complete\ndata: {json.dumps({'success': True, 'extracted': progress.extracted})}\n\n"
                        else:
                            yield f"event: error\ndata: {json.dumps({'error': progress.error})}\n\n"
                        break

                except asyncio.TimeoutError:
                    yield f"event: ping\ndata: {json.dumps({'status': 'alive'})}\n\n"

        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.post("/extract/cancel")
async def cancel_voice_extraction():
    """추출 취소"""
    global _extract_task, _extract_cancel_flag

    if _extract_task is None or _extract_task.done():
        raise HTTPException(status_code=404, detail="진행 중인 추출이 없습니다")

    _extract_cancel_flag = True

    return {"status": "cancelling", "message": "추출 취소 요청됨"}


@router.get("/extract/check-source")
async def check_voice_assets():
    """Assets/Voice 폴더 상태 확인"""
    voice_assets_dir = Path("Assets/Voice")

    if not voice_assets_dir.exists():
        return {
            "exists": False,
            "message": "Assets/Voice 폴더가 없습니다",
            "hint": "게임 클라이언트의 files/bundles/audio/sound_beta_2/voice_kr 등을 Assets/Voice/voice_kr 등으로 복사해주세요"
        }

    from ...common.language_codes import normalize_voice_folder

    languages = {}
    for lang_dir in voice_assets_dir.iterdir():
        if lang_dir.is_dir():
            ab_count = len(list(lang_dir.glob("*.ab")))
            if ab_count > 0:
                # voice_jp/voice_ja → voice (일본어 정규화)
                canonical = normalize_voice_folder(lang_dir.name)
                languages[canonical] = languages.get(canonical, 0) + ab_count

    return {
        "exists": True,
        "path": str(voice_assets_dir.absolute()),
        "languages": languages,
        "total_bundles": sum(languages.values())
    }


# ============================================================================
# 이미지 추출 관련 엔드포인트
# ============================================================================

# 이미지 추출 작업 상태
_image_extract_task: Optional[asyncio.Task] = None
_image_extract_progress_queue: Optional[asyncio.Queue] = None
_image_extract_cancel_flag = False


class ImageExtractProgress(BaseModel):
    """이미지 추출 진행 상태"""
    stage: str  # scanning, extracting, complete, error
    current_file: Optional[str] = None
    processed: int = 0
    total: int = 0
    extracted: int = 0
    message: str = ""
    error: Optional[str] = None


@router.get("/extract/images/check-source")
async def check_image_assets():
    """Assets/Image 폴더 상태 확인"""
    image_assets_dir = Path("Assets/Image")

    # avg/characters 폴더 확인
    characters_dir = image_assets_dir / "avg" / "characters"
    characters_count = len(list(characters_dir.glob("*.ab"))) if characters_dir.exists() else 0

    # chararts 폴더 확인
    chararts_dir = image_assets_dir / "chararts"
    chararts_count = len(list(chararts_dir.glob("*.ab"))) if chararts_dir.exists() else 0

    return {
        "exists": True,
        "path": str(image_assets_dir.absolute()),
        "characters_exists": characters_count > 0,
        "characters_bundles": characters_count,
        "chararts_exists": chararts_count > 0,
        "chararts_bundles": chararts_count,
        "total_bundles": characters_count + chararts_count,
    }


@router.get("/extract/images/status")
async def get_image_extract_status():
    """이미지 추출 작업 상태 확인"""
    global _image_extract_task

    if _image_extract_task is None:
        return {"status": "idle", "message": "대기 중"}

    if _image_extract_task.done():
        try:
            result = _image_extract_task.result()
            return {"status": "complete", "result": result}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    return {"status": "running", "message": "추출 진행 중"}


@router.post("/extract/images/start")
async def start_image_extraction(target: str = "all"):
    """이미지 추출 시작. target: 'characters', 'chararts', 'all'"""
    global _image_extract_task, _image_extract_progress_queue, _image_extract_cancel_flag

    if target not in ("characters", "chararts", "all"):
        raise HTTPException(status_code=400, detail="target은 'characters', 'chararts', 'all' 중 하나여야 합니다")

    # 이미 추출 중인지 확인
    if _image_extract_task and not _image_extract_task.done():
        raise HTTPException(status_code=409, detail="이미 추출이 진행 중입니다")

    # Assets/Image 경로 확인
    image_assets_dir = Path("Assets/Image")
    characters_dir = image_assets_dir / "avg" / "characters"
    chararts_dir = image_assets_dir / "chararts"

    # 대상에 따른 폴더 확인
    need_characters = target in ("characters", "all")
    need_chararts = target in ("chararts", "all")

    if need_characters and not characters_dir.exists() and need_chararts and not chararts_dir.exists():
        raise HTTPException(
            status_code=404,
            detail="Assets/Image/avg/characters 또는 Assets/Image/chararts 폴더가 없습니다."
        )
    if need_characters and not need_chararts and not characters_dir.exists():
        raise HTTPException(status_code=404, detail="Assets/Image/avg/characters 폴더가 없습니다.")
    if need_chararts and not need_characters and not chararts_dir.exists():
        raise HTTPException(status_code=404, detail="Assets/Image/chararts 폴더가 없습니다.")

    # 진행률 큐 생성
    _image_extract_progress_queue = asyncio.Queue()
    _image_extract_cancel_flag = False

    async def extract_task():
        from src.tools.extractor.image import extract_images_from_bundle

        stats = {"processed": 0, "extracted": 0, "failed": 0}

        try:
            # 스캔 단계
            await _image_extract_progress_queue.put(ImageExtractProgress(
                stage="scanning",
                message="번들 파일 스캔 중..."
            ))

            # 추출 작업 목록 생성: (소스 폴더, 출력 폴더, 번들 파일들)
            extract_jobs: list[tuple[Path, Path, list[Path]]] = []

            # avg/characters → extracted/images/characters
            if need_characters and characters_dir.exists():
                ab_files = list(characters_dir.glob("*.ab"))
                if ab_files:
                    output_dir = Path("extracted/images/characters")
                    output_dir.mkdir(parents=True, exist_ok=True)
                    extract_jobs.append((characters_dir, output_dir, ab_files))

            # chararts → extracted/images/chararts
            if need_chararts and chararts_dir.exists():
                ab_files = list(chararts_dir.glob("*.ab"))
                if ab_files:
                    output_dir = Path("extracted/images/chararts")
                    output_dir.mkdir(parents=True, exist_ok=True)
                    extract_jobs.append((chararts_dir, output_dir, ab_files))

            # 전체 파일 수 계산
            total = sum(len(job[2]) for job in extract_jobs)
            current = 0

            for source_dir, output_dir, ab_files in extract_jobs:
                source_name = source_dir.name  # "characters" or "chararts"

                for ab_path in ab_files:
                    if _image_extract_cancel_flag:
                        break

                    current += 1

                    # 진행률 전송
                    await _image_extract_progress_queue.put(ImageExtractProgress(
                        stage="extracting",
                        current_file=f"[{source_name}] {ab_path.name}",
                        processed=current,
                        total=total,
                        extracted=stats["extracted"],
                        message=f"[{source_name}] {ab_path.name} 처리 중..."
                    ))

                    try:
                        # 동기 함수를 별도 스레드에서 실행
                        extracted = await asyncio.get_event_loop().run_in_executor(
                            None,
                            extract_images_from_bundle,
                            ab_path,
                            output_dir,
                            "png"
                        )
                        stats["processed"] += 1
                        stats["extracted"] += len(extracted)
                    except Exception:
                        stats["failed"] += 1

            # 완료 - 이미지 프로바이더 캐시 리셋
            from .voice import reset_image_provider
            reset_image_provider()

            await _image_extract_progress_queue.put(ImageExtractProgress(
                stage="complete",
                processed=stats["processed"],
                total=total,
                extracted=stats["extracted"],
                message=f"추출 완료: {stats['extracted']}개 이미지"
            ))

            return stats

        except Exception as e:
            logger.error("이미지 추출 실패: %s", e, exc_info=True)
            await _image_extract_progress_queue.put(ImageExtractProgress(
                stage="error",
                error=str(e),
                message="추출 실패"
            ))
            raise

    _image_extract_task = asyncio.create_task(extract_task())

    return {"status": "started", "message": "이미지 추출이 시작되었습니다 (characters + chararts)"}


@router.get("/extract/images/stream")
async def stream_image_extract_progress():
    """이미지 추출 진행률 SSE 스트림"""
    global _image_extract_progress_queue

    if _image_extract_progress_queue is None:
        raise HTTPException(status_code=404, detail="진행 중인 추출이 없습니다")

    async def event_generator():
        try:
            while True:
                try:
                    progress = await asyncio.wait_for(
                        _image_extract_progress_queue.get(),
                        timeout=30.0
                    )

                    data = progress.model_dump() if hasattr(progress, 'model_dump') else progress.__dict__
                    yield f"event: progress\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

                    if progress.stage in ("complete", "error"):
                        if progress.stage == "complete":
                            yield f"event: complete\ndata: {json.dumps({'success': True, 'extracted': progress.extracted})}\n\n"
                        else:
                            yield f"event: error\ndata: {json.dumps({'error': progress.error})}\n\n"
                        break

                except asyncio.TimeoutError:
                    yield f"event: ping\ndata: {json.dumps({'status': 'alive'})}\n\n"

        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.post("/extract/images/cancel")
async def cancel_image_extraction():
    """이미지 추출 취소"""
    global _image_extract_task, _image_extract_cancel_flag

    if _image_extract_task is None or _image_extract_task.done():
        raise HTTPException(status_code=404, detail="진행 중인 추출이 없습니다")

    _image_extract_cancel_flag = True

    return {"status": "cancelling", "message": "추출 취소 요청됨"}


# ============================================================================
# GPU 세마포어 설정
# ============================================================================

@router.get("/gpu-semaphore")
async def get_gpu_semaphore_status():
    """GPU 세마포어 상태 조회"""
    from .. import is_gpu_semaphore_enabled
    return {
        "enabled": is_gpu_semaphore_enabled(),
        "description": "활성화 시 OCR과 TTS가 동시에 실행되지 않음 (GPU 메모리 보호)"
    }


@router.post("/gpu-semaphore")
async def set_gpu_semaphore_status(enabled: bool):
    """GPU 세마포어 활성화/비활성화"""
    from .. import set_gpu_semaphore_enabled
    set_gpu_semaphore_enabled(enabled)
    return {
        "enabled": enabled,
        "message": f"GPU 세마포어 {'활성화' if enabled else '비활성화'}됨"
    }


# ============================================================================
# TTS 엔진 설정
# ============================================================================


class TTSEngineSettingResponse(BaseModel):
    """TTS 엔진 설정 응답"""
    engine: str
    available_engines: list[str]
    engine_status: dict


@router.get("/tts-engine")
async def get_tts_engine_setting():
    """기본 TTS 엔진 설정 조회"""
    # 사용 가능한 엔진 확인
    available_engines = []
    engine_status = {}

    # GPT-SoVITS 확인
    gpt_status = check_gpt_sovits()
    engine_status["gpt_sovits"] = {
        "installed": gpt_status.installed,
        "name": "GPT-SoVITS",
        "description": "고품질 음성 클로닝. 캐릭터별 학습 필요, 학습 후 최상의 품질.",
    }
    if gpt_status.installed:
        available_engines.append("gpt_sovits")

    return TTSEngineSettingResponse(
        engine=config.default_tts_engine,
        available_engines=available_engines,
        engine_status=engine_status,
    )


class SetTTSEngineRequest(BaseModel):
    """TTS 엔진 설정 요청"""
    engine: str


@router.post("/tts-engine")
async def set_tts_engine_setting(request: SetTTSEngineRequest):
    """기본 TTS 엔진 설정 변경"""
    valid_engines = ["gpt_sovits"]
    if request.engine not in valid_engines:
        raise HTTPException(
            status_code=400,
            detail=f"유효하지 않은 엔진: {request.engine}. 가능한 값: {valid_engines}"
        )

    # 설정 변경
    config.default_tts_engine = request.engine
    config.save()

    return {
        "engine": request.engine,
        "message": f"TTS 엔진이 'GPT-SoVITS'(으)로 변경되었습니다"
    }
