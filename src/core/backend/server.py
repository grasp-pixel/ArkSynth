"""FastAPI 서버 정의"""

import logging
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


def create_app() -> FastAPI:
    """FastAPI 앱 생성"""
    setup_file_logging()
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
