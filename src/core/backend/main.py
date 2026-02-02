"""AVT 백엔드 서버 메인"""

import sys
import uvicorn

from .config import config
from .server import create_app


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
    app = create_app()
    uvicorn.run(
        app,
        host=config.host,
        port=config.port,
        reload=config.debug,
    )


if __name__ == "__main__":
    main()
