"""ArkSynth 백엔드 서버 메인"""

import logging
import sys

import uvicorn

from .config import config
from .server import create_app


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


def main():
    """서버 실행"""
    _setup_console_encoding()
    app = create_app()  # create_app() 내부에서 setup_file_logging() 호출
    logging.getLogger("uvicorn.access").addFilter(_ImageLogFilter())
    uvicorn.run(
        app,
        host=config.host,
        port=config.port,
        reload=config.debug,
    )


if __name__ == "__main__":
    main()
