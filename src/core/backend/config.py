"""서버 설정"""

from pathlib import Path
from pydantic import BaseModel


class ServerConfig(BaseModel):
    """서버 설정"""

    host: str = "127.0.0.1"
    port: int = 8000
    debug: bool = False

    # 경로 설정
    data_path: Path = Path("data")  # gamedata, gamedata_yostar 포함
    extracted_path: Path = Path("extracted")
    models_path: Path = Path("models")
    rendered_path: Path = Path("rendered")

    # TTS 설정
    default_voice: str = "ko-KR-SunHiNeural"
    default_language: str = "ko_KR"


# 전역 설정 인스턴스
config = ServerConfig()
