"""서버 설정"""

import json
import logging
from pathlib import Path
from pydantic import BaseModel

from ..common.language_codes import short_to_voice_folder, short_to_locale, locale_to_server

logger = logging.getLogger(__name__)

# 저장 대상 필드 (사용자가 변경하는 설정만)
_PERSIST_FIELDS = {
    "display_language",
    "voice_language_short",
    "gamedata_source",
    "gamedata_repo",
    "gamedata_branch",
    "default_tts_engine",
    "nickname",
    "gpu_half_precision",
    "vram_cleanup_after_whisper",
    "whisper_float32",
    "cuda_memory_optimization",
}

CONFIG_FILE = Path("data/config.json")


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
    game_language: str = "kr"  # 서버 코드 (kr, jp, en)
    voice_language: str = "voice_kr"  # voice_language_short에서 파생
    gpt_sovits_language: str = "ko"  # voice_language_short와 동기

    # 게임 데이터 다운로드 설정
    gamedata_source: str = "arkprts"  # "github" 또는 "arkprts"
    gamedata_repo: str = "ArknightsAssets/ArknightsGamedata"  # GitHub owner/repo
    gamedata_branch: str = "master"

    # 닉네임 ({@nickname} 템플릿 치환용, 언어별)
    nickname: dict[str, str] = {"ko": "오라클", "ja": "オラクル", "en": "Oracle"}

    # GPU 호환성 설정
    gpu_half_precision: bool = True  # True=FP16(기본), False=FP32
    vram_cleanup_after_whisper: bool = False  # Whisper 언로드 후 VRAM 정리
    whisper_float32: bool = False  # Whisper compute_type=float32
    cuda_memory_optimization: bool = False  # PYTORCH_CUDA_ALLOC_CONF 최적화

    # TTS 설정
    default_voice: str = "ko-KR-SunHiNeural"
    default_tts_language: str = "ko-KR"  # Edge TTS 언어
    default_tts_engine: str = "gpt_sovits"  # 기본 TTS 엔진

    # 업데이트 설정
    update_repo: str = "grasp-pixel/ArkSynth"  # GitHub owner/repo

    def get_nickname(self, lang_short: str) -> str:
        """언어별 닉네임 반환 (빈 문자열이면 빈 문자열 반환)"""
        return self.nickname.get(lang_short, "")

    def apply_display_language(self, locale: str) -> None:
        """표시 언어 변경 시 관련 필드 일괄 갱신"""
        self.display_language = locale
        self.game_language = locale_to_server(locale)
        self.save()

    def apply_voice_language(self, short: str) -> None:
        """음성 언어 변경 시 관련 필드 일괄 갱신"""
        self.voice_language_short = short
        self.voice_language = short_to_voice_folder(short)
        self.gpt_sovits_language = short
        self.save()

    def _sync_derived_fields(self) -> None:
        """저장된 기본 필드에서 파생 필드 재계산"""
        self.game_language = locale_to_server(self.display_language)
        self.voice_language = short_to_voice_folder(self.voice_language_short)
        self.gpt_sovits_language = self.voice_language_short

    def save(self) -> None:
        """설정을 JSON 파일로 저장"""
        try:
            data = {k: getattr(self, k) for k in _PERSIST_FIELDS}
            CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            CONFIG_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning(f"설정 저장 실패: {e}")

    def load(self) -> None:
        """JSON 파일에서 설정 로드"""
        if not CONFIG_FILE.exists():
            return
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            # 하위 호환: nickname이 str이면 dict로 마이그레이션
            if isinstance(data.get("nickname"), str):
                old = data["nickname"]
                data["nickname"] = {"ko": old, "ja": "", "en": ""}
            for key, value in data.items():
                if key in _PERSIST_FIELDS and hasattr(self, key):
                    setattr(self, key, value)
            self._sync_derived_fields()
            logger.info(f"설정 로드: display={self.display_language}, voice={self.voice_language_short}")
        except Exception as e:
            logger.warning(f"설정 로드 실패: {e}")


_VERSION_CANDIDATES = (Path("version.json"), Path("app/version.json"))


def get_app_version() -> str:
    """version.json에서 앱 버전 읽기"""
    for candidate in _VERSION_CANDIDATES:
        if candidate.exists():
            try:
                return json.loads(candidate.read_text(encoding="utf-8"))["version"]
            except Exception:
                pass
    return "0.0.0"


# 전역 설정 인스턴스
config = ServerConfig()
config.load()
