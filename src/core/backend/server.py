"""FastAPI 서버 정의"""

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .routes import episodes, stories, tts, voice, health, ocr, training, render, settings, data, aliases

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """FastAPI 앱 생성"""
    app = FastAPI(
        title="ArkSynth API",
        description="ArkSynth API - 명일방주 스토리 음성 더빙",
        version="0.1.0",
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

    return app
