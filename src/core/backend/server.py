"""FastAPI 서버 정의"""

import logging
import os
import platform
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_app_version
from .routes import episodes, stories, tts, voice, health, ocr, training, render, settings, data, aliases, update

logger = logging.getLogger(__name__)

LOG_DIR = Path("logs")

_file_logging_initialized = False


def setup_file_logging() -> None:
    """파일 로깅 설정 (RotatingFileHandler)

    여러 진입점(main.py, uvicorn --factory)에서 호출되어도
    한 번만 초기화됩니다.
    """
    global _file_logging_initialized
    if _file_logging_initialized:
        return
    _file_logging_initialized = True

    LOG_DIR.mkdir(exist_ok=True)
    handler = RotatingFileHandler(
        LOG_DIR / "backend.log",
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=2,  # 최대 3개 파일 보존
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    ))
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(logging.INFO)


def _log_system_info() -> None:
    """시스템 사양 로깅"""
    lines = [f"ArkSynth v{get_app_version()}"]

    # OS
    lines.append(f"OS: {platform.system()} {platform.release()} ({platform.machine()})")

    # Python
    lines.append(f"Python: {sys.version.split()[0]}")

    # CPU
    cpu_name = platform.processor() or "Unknown"
    try:
        cpu_count = os.cpu_count() or 0
        lines.append(f"CPU: {cpu_name} ({cpu_count} cores)")
    except Exception:
        lines.append(f"CPU: {cpu_name}")

    # RAM
    try:
        import psutil
        mem = psutil.virtual_memory()
        lines.append(f"RAM: {mem.total / (1024**3):.1f}GB (available {mem.available / (1024**3):.1f}GB)")
    except ImportError:
        pass

    # GPU
    try:
        import torch
        if torch.cuda.is_available():
            # 지원 아키텍처 목록
            try:
                arch_list = torch.cuda.get_arch_list()
                supported_sms = [
                    int(a.replace("sm_", "").rstrip("a"))
                    for a in arch_list if a.startswith("sm_")
                ]
                max_sm = max(supported_sms) if supported_sms else 0
            except Exception:
                supported_sms, max_sm = [], 0

            for i in range(torch.cuda.device_count()):
                props = torch.cuda.get_device_properties(i)
                vram_gb = props.total_memory / (1024**3)
                free, _ = torch.cuda.mem_get_info(i)
                free_gb = free / (1024**3)
                gpu_sm = props.major * 10 + props.minor
                lines.append(
                    f"GPU[{i}]: {props.name} "
                    f"(VRAM {vram_gb:.1f}GB, free {free_gb:.1f}GB, "
                    f"sm_{gpu_sm})"
                )
                if max_sm and gpu_sm > max_sm:
                    lines.append(
                        f"  !! GPU 비호환: sm_{gpu_sm}은 현재 "
                        f"PyTorch({torch.__version__})에서 지원되지 않습니다. "
                        f"(최대 sm_{max_sm})"
                    )
                    lines.append(
                        "  -> PyTorch 2.7.0+cu128 이상으로 업그레이드가 필요합니다."
                    )
            lines.append(f"PyTorch: {torch.__version__} (CUDA {torch.version.cuda})")
        else:
            lines.append("GPU: CUDA not available")
            lines.append(f"PyTorch: {torch.__version__}")
    except ImportError:
        lines.append("GPU: torch not installed")

    header = "=" * 50
    logger.info(f"\n{header}\n" + "\n".join(lines) + f"\n{header}")


def create_app() -> FastAPI:
    """FastAPI 앱 생성"""
    setup_file_logging()
    _log_system_info()
    app = FastAPI(
        title="ArkSynth API",
        description="ArkSynth API - 명일방주 스토리 음성 더빙",
        version=get_app_version(),
    )

    @app.exception_handler(FileNotFoundError)
    async def file_not_found_handler(request: Request, exc: FileNotFoundError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error("%s %s - %s: %s", request.method, request.url.path, type(exc).__name__, exc)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    # CORS 설정 (Electron 프론트엔드 허용)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 라우터 등록
    app.include_router(health.router, tags=["health"])
    app.include_router(episodes.router, prefix="/api/episodes", tags=["episodes"])
    app.include_router(stories.router, prefix="/api/stories", tags=["stories"])
    app.include_router(tts.router, prefix="/api/tts", tags=["tts"])
    app.include_router(voice.router, prefix="/api/voice", tags=["voice"])
    app.include_router(ocr.router, prefix="/api/ocr", tags=["ocr"])
    app.include_router(training.router, prefix="/api/training", tags=["training"])
    app.include_router(render.router, prefix="/api/render", tags=["render"])
    app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
    app.include_router(data.router, prefix="/api/data", tags=["data"])
    app.include_router(aliases.router, prefix="/api/aliases", tags=["aliases"])
    app.include_router(update.router, prefix="/api/update", tags=["update"])

    return app
