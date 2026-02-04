"""설정 관련 라우터"""

import asyncio
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..config import config

router = APIRouter()

# 설치 작업 상태
_install_task: Optional[asyncio.Task] = None
_install_progress_queue: Optional[asyncio.Queue] = None


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
    game_language: str
    voice_language: str
    gpt_sovits_language: str

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


def check_flatc() -> DependencyStatus:
    """FlatBuffers Compiler (flatc) 설치 확인

    arkprts 라이브러리가 게임 데이터를 파싱하는 데 필요합니다.
    """
    try:
        result = subprocess.run(
            ["flatc", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            # 버전 추출 (예: "flatc version 24.3.25")
            version_line = result.stdout.strip()
            version = "unknown"
            if "version" in version_line.lower():
                parts = version_line.split()
                for i, p in enumerate(parts):
                    if p.lower() == "version" and i + 1 < len(parts):
                        version = parts[i + 1]
                        break
            path = shutil.which("flatc")
            return DependencyStatus(
                name="flatc",
                installed=True,
                version=version,
                path=path,
            )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return DependencyStatus(name="flatc", installed=False)


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
        check_flatc(),
        check_gpt_sovits(),
    ]

    return SettingsResponse(
        gpt_sovits_path=str(gpt_config.gpt_sovits_path),
        models_path=str(config.models_path),
        extracted_path=str(config.extracted_path),
        gamedata_path=str(config.gamedata_yostar_path),
        game_language=config.game_language,
        voice_language=config.voice_language,
        gpt_sovits_language=config.gpt_sovits_language,
        whisper_model_size=gpt_config.whisper_model_size,
        whisper_compute_type=gpt_config.whisper_compute_type,
        use_whisper_preprocessing=gpt_config.use_whisper_preprocessing,
        dependencies=dependencies,
    )


@router.get("/dependencies")
async def check_dependencies():
    """의존성 상태만 확인"""
    return {
        "dependencies": [
            check_ffmpeg(),
            check_ffprobe(),
            check_7zip(),
            check_flatc(),
            check_gpt_sovits(),
        ]
    }


@router.post("/open-folder")
async def open_folder(path: str):
    """폴더 열기 (탐색기)"""
    folder = Path(path)
    if not folder.exists():
        raise HTTPException(status_code=404, detail=f"폴더가 존재하지 않습니다: {path}")

    try:
        if sys.platform == "win32":
            subprocess.Popen(["explorer", str(folder)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(folder)])
        else:
            subprocess.Popen(["xdg-open", str(folder)])
        return {"status": "ok"}
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


@router.get("/flatc/install-guide")
async def flatc_install_guide():
    """FlatBuffers Compiler 설치 가이드"""
    return {
        "name": "flatc (FlatBuffers Compiler)",
        "description": "arkprts 라이브러리가 게임 데이터 파싱 시 FlatBuffers 스키마를 컴파일하는 데 필요합니다.",
        "windows": {
            "method": "winget",
            "command": "winget install Google.FlatBuffers",
            "alternative": "https://github.com/google/flatbuffers/releases 에서 다운로드",
        },
        "manual_steps": [
            "1. https://github.com/google/flatbuffers/releases 에서 최신 릴리스 다운로드",
            "2. Windows.flatc.binary.zip 파일 선택",
            "3. 압축 해제 후 flatc.exe를 PATH가 포함된 폴더에 복사",
            "4. 터미널 재시작 후 'flatc --version'으로 확인",
        ],
        "required_for": "게임 데이터 업데이트 (arkprts)",
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

        all_stats = {}
        total_extracted = 0

        try:
            for lang in request.languages:
                if _extract_cancel_flag:
                    break

                lang_source = voice_assets_dir / lang
                if not lang_source.exists():
                    continue

                lang_output = config.extracted_path / lang

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

    languages = {}
    for lang_dir in voice_assets_dir.iterdir():
        if lang_dir.is_dir():
            ab_count = len(list(lang_dir.glob("*.ab")))
            if ab_count > 0:
                languages[lang_dir.name] = ab_count

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

    if not image_assets_dir.exists():
        return {
            "exists": False,
            "message": "Assets/Image 폴더가 없습니다",
            "hint": "게임 클라이언트의 files/bundles/avg/characters 번들을 Assets/Image/avg/characters로 복사해주세요"
        }

    # avg/characters 폴더 확인
    characters_dir = image_assets_dir / "avg" / "characters"
    if not characters_dir.exists():
        return {
            "exists": True,
            "path": str(image_assets_dir.absolute()),
            "characters_exists": False,
            "total_bundles": 0
        }

    ab_count = len(list(characters_dir.glob("*.ab")))

    return {
        "exists": True,
        "path": str(image_assets_dir.absolute()),
        "characters_exists": True,
        "total_bundles": ab_count
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
async def start_image_extraction():
    """이미지 추출 시작"""
    global _image_extract_task, _image_extract_progress_queue, _image_extract_cancel_flag

    # 이미 추출 중인지 확인
    if _image_extract_task and not _image_extract_task.done():
        raise HTTPException(status_code=409, detail="이미 추출이 진행 중입니다")

    # Assets/Image 경로 확인
    image_assets_dir = Path("Assets/Image")
    characters_dir = image_assets_dir / "avg" / "characters"

    if not characters_dir.exists():
        raise HTTPException(
            status_code=404,
            detail="Assets/Image/avg/characters 폴더가 없습니다."
        )

    # 진행률 큐 생성
    _image_extract_progress_queue = asyncio.Queue()
    _image_extract_cancel_flag = False

    async def extract_task():
        from src.tools.extractor.image import extract_images_from_bundle

        output_dir = Path("extracted/images/characters")
        output_dir.mkdir(parents=True, exist_ok=True)

        stats = {"processed": 0, "extracted": 0, "failed": 0}

        try:
            # 스캔 단계
            await _image_extract_progress_queue.put(ImageExtractProgress(
                stage="scanning",
                message="번들 파일 스캔 중..."
            ))

            ab_files = list(characters_dir.glob("*.ab"))
            total = len(ab_files)

            for i, ab_path in enumerate(ab_files, 1):
                if _image_extract_cancel_flag:
                    break

                # 진행률 전송
                await _image_extract_progress_queue.put(ImageExtractProgress(
                    stage="extracting",
                    current_file=ab_path.name,
                    processed=i,
                    total=total,
                    extracted=stats["extracted"],
                    message=f"{ab_path.name} 처리 중..."
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

            # 완료
            await _image_extract_progress_queue.put(ImageExtractProgress(
                stage="complete",
                processed=stats["processed"],
                total=total,
                extracted=stats["extracted"],
                message=f"추출 완료: {stats['extracted']}개 이미지"
            ))

            return stats

        except Exception as e:
            await _image_extract_progress_queue.put(ImageExtractProgress(
                stage="error",
                error=str(e),
                message="추출 실패"
            ))
            raise

    _image_extract_task = asyncio.create_task(extract_task())

    return {"status": "started", "message": "이미지 추출이 시작되었습니다"}


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
