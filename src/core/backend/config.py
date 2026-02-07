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
    gamedata_path: Path = Path("data/gamedata")  # 중국어 원본 데이터
    gamedata_yostar_path: Path = Path("data/gamedata_yostar")  # 글로벌 서버 데이터
    extracted_path: Path = Path("extracted")
    models_path: Path = Path("models")
    rendered_path: Path = Path("rendered")

    # 언어 설정 (앱 전체에서 사용)
    game_language: str = "ko_KR"  # 게임 데이터 언어 (캐릭터 이름 등)
    voice_language: str = "voice_kr"  # 음성 폴더 (voice, voice_kr, voice_cn, voice_en)

    # 게임 데이터 다운로드 설정
    gamedata_repo: str = "ArknightsAssets/ArknightsGamedata"  # GitHub owner/repo
    gamedata_branch: str = "master"

    # TTS 설정
    default_voice: str = "ko-KR-SunHiNeural"
    default_tts_language: str = "ko-KR"  # Edge TTS 언어
    gpt_sovits_language: str = "ko"  # GPT-SoVITS 언어 (ko, ja, zh, en)
    default_tts_engine: str = "gpt_sovits"  # 기본 TTS 엔진


# 전역 설정 인스턴스
config = ServerConfig()
