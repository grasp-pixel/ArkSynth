"""ArkSynth 백엔드 서버 메인"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

import uvicorn

from .config import config
from .server import create_app

LOG_DIR = Path("logs")


class _ImageLogFilter(logging.Filter):
    """이미지 요청의 액세스 로그를 숨기는 필터"""

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        if "/api/voice/images/" in msg or "/api/voice/portraits/" in msg:
            return False
        return True


def _setup_console_encoding():
    """Windows 콘솔 UTF-8 인코딩 설정"""
    if sys.platform == "win32":
        try:
            import ctypes
            # Windows 콘솔 출력 코드 페이지를 UTF-8(65001)로 설정
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleOutputCP(65001)
            kernel32.SetConsoleCP(65001)
        except Exception:
            pass  # 콘솔이 없는 환경에서는 무시


def _setup_file_logging():
    """파일 로깅 설정 (RotatingFileHandler)"""
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


def main():
    """서버 실행"""
    _setup_console_encoding()
    _setup_file_logging()
    app = create_app()
    logging.getLogger("uvicorn.access").addFilter(_ImageLogFilter())
    uvicorn.run(
        app,
        host=config.host,
        port=config.port,
        reload=config.debug,
    )


if __name__ == "__main__":
    main()
