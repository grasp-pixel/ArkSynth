"""AVT 백엔드 서버 메인"""

import uvicorn

from .config import config
from .server import create_app


def main():
    """서버 실행"""
    app = create_app()
    uvicorn.run(
        app,
        host=config.host,
        port=config.port,
        reload=config.debug,
    )


if __name__ == "__main__":
    main()
