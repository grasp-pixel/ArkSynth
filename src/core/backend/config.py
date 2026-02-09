"""서버 설정"""

from pathlib import Path
from pydantic import BaseModel

from ..common.language_codes import short_to_voice_folder, short_to_locale


class ServerConfig(BaseModel):
    """서버 설정"""

    host: str = "127.0.0.1"
    port: int = 8000
    debug: bool = False

    # 경로 설정
    data_path: Path = Path("data")  # gamedata 포함
    gamedata_path: Path = Path("data/gamedata")  # 게임 데이터 (서버별: kr, cn, jp, en)
    extracted_path: Path = Path("extracted")
    models_path: Path = Path("models")
    rendered_path: Path = Path("rendered")

    # === 언어 설정 ===
    # 표시 언어 (스토리 텍스트 + UI)
    display_language: str = "ko_KR"  # 로케일 코드 (ko_KR, ja_JP, en_US)
    # 음성 언어 (단축 코드)
    voice_language_short: str = "ko"  # 단축 코드 (ko, ja, en)

    # 하위 호환 필드 (apply_* 메서드로 동기화)
    game_language: str = "ko_KR"  # display_language와 동기
    voice_language: str = "voice_kr"  # voice_language_short에서 파생
    gpt_sovits_language: str = "ko"  # voice_language_short와 동기

    # 게임 데이터 다운로드 설정
    gamedata_source: str = "arkprts"  # "github" 또는 "arkprts"
    gamedata_repo: str = "ArknightsAssets/ArknightsGamedata"  # GitHub owner/repo
    gamedata_branch: str = "master"

    # TTS 설정
    default_voice: str = "ko-KR-SunHiNeural"
    default_tts_language: str = "ko-KR"  # Edge TTS 언어
    default_tts_engine: str = "gpt_sovits"  # 기본 TTS 엔진

    def apply_display_language(self, locale: str) -> None:
        """표시 언어 변경 시 관련 필드 일괄 갱신"""
        self.display_language = locale
        self.game_language = locale

    def apply_voice_language(self, short: str) -> None:
        """음성 언어 변경 시 관련 필드 일괄 갱신"""
        self.voice_language_short = short
        self.voice_language = short_to_voice_folder(short)
        self.gpt_sovits_language = short


# 전역 설정 인스턴스
config = ServerConfig()
