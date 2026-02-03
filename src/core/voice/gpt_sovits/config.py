"""GPT-SoVITS 설정"""

import os
from dataclasses import dataclass, field
from pathlib import Path


# 기본 설치 경로 (앱 내 자동 설치 위치)
DEFAULT_INSTALL_BASE = Path("tools/gpt_sovits")
# 통합 패키지 경로 (Hugging Face에서 다운로드) - v2pro 최신
INTEGRATED_PACKAGE_PATH = DEFAULT_INSTALL_BASE / "GPT-SoVITS-v2pro-20250604"
# 레거시 통합 패키지 경로
LEGACY_INTEGRATED_PATH = DEFAULT_INSTALL_BASE / "GPT-SoVITS-v2-240821"
# 소스 설치 경로 (레거시)
SOURCE_INSTALL_PATH = DEFAULT_INSTALL_BASE / "GPT-SoVITS-main"


def _get_default_gpt_sovits_path() -> Path:
    """GPT-SoVITS 기본 경로 결정

    우선순위:
    1. 환경변수 GPT_SOVITS_PATH
    2. 최신 통합 패키지 경로 (tools/gpt_sovits/GPT-SoVITS-v2pro-20250604)
    3. 레거시 통합 패키지 경로 (tools/gpt_sovits/GPT-SoVITS-v2-240821)
    4. 소스 설치 경로 (tools/gpt_sovits/GPT-SoVITS-main)
    5. 레거시 경로 (C:/GPT-SoVITS)
    """
    # 환경변수 우선
    env_path = os.environ.get("GPT_SOVITS_PATH")
    if env_path:
        return Path(env_path)

    # 최신 통합 패키지 경로 확인 (권장)
    if INTEGRATED_PACKAGE_PATH.exists():
        return INTEGRATED_PACKAGE_PATH

    # 레거시 통합 패키지 경로 확인
    if LEGACY_INTEGRATED_PATH.exists():
        return LEGACY_INTEGRATED_PATH

    # 소스 설치 경로 확인
    if SOURCE_INSTALL_PATH.exists():
        return SOURCE_INSTALL_PATH

    # 레거시 경로 확인
    legacy_path = Path("C:/GPT-SoVITS")
    if legacy_path.exists():
        return legacy_path

    # 기본값 (최신 통합 패키지가 설치될 경로)
    return INTEGRATED_PACKAGE_PATH


@dataclass
class GPTSoVITSConfig:
    """GPT-SoVITS 학습 및 추론 설정"""

    # GPT-SoVITS 설치 경로
    gpt_sovits_path: Path = field(
        default_factory=_get_default_gpt_sovits_path
    )

    # API 서버 설정
    api_host: str = "127.0.0.1"
    api_port: int = 9880

    # 경로 설정
    models_path: Path = field(default_factory=lambda: Path("models/gpt_sovits"))
    extracted_path: Path = field(default_factory=lambda: Path("extracted"))
    pretrained_path: Path = field(
        default_factory=lambda: Path("models/gpt_sovits/pretrained")
    )

    # 학습 설정
    epochs_sovits: int = 8  # SoVITS 학습 에포크
    epochs_gpt: int = 15  # GPT 학습 에포크
    batch_size: int = 4
    learning_rate: float = 0.0001

    # 오디오 설정
    sample_rate: int = 32000  # GPT-SoVITS 기본
    hop_length: int = 640
    win_length: int = 2048

    # 추론 설정
    top_k: int = 5
    top_p: float = 1.0
    temperature: float = 1.0

    # 언어 설정 (한국어 우선)
    default_language: str = "ko"

    # 참조 오디오 설정
    min_ref_audio_length: float = 3.0  # 최소 참조 오디오 길이 (초)
    max_ref_audio_length: float = 20.0  # 최대 참조 오디오 길이 (초)
    ref_audio_count: int = 5  # 학습에 사용할 참조 오디오 개수

    @property
    def api_url(self) -> str:
        """GPT-SoVITS API 서버 URL"""
        return f"http://{self.api_host}:{self.api_port}"

    @property
    def is_gpt_sovits_installed(self) -> bool:
        """GPT-SoVITS 설치 여부 확인"""
        # api_v2.py 또는 api.py 존재 확인
        return (
            (self.gpt_sovits_path / "api_v2.py").exists() or
            (self.gpt_sovits_path / "api.py").exists()
        )

    @property
    def python_path(self) -> Path | None:
        """GPT-SoVITS용 Python 실행 파일 경로

        우선순위:
        1. 통합 패키지 runtime (gpt_sovits_path/runtime/python.exe) - 권장
        2. 소스 설치 venv (gpt_sovits_path/.venv/Scripts/python.exe)
        """
        # 통합 패키지 runtime (권장)
        runtime_python = self.gpt_sovits_path / "runtime" / "python.exe"
        if runtime_python.exists():
            return runtime_python

        # 소스 설치 venv (레거시)
        venv_python = self.gpt_sovits_path / ".venv" / "Scripts" / "python.exe"
        if venv_python.exists():
            return venv_python

        return None

    @property
    def install_base_path(self) -> Path:
        """자동 설치 기본 경로"""
        return DEFAULT_INSTALL_BASE

    def ensure_directories(self):
        """필요한 디렉토리 생성"""
        self.models_path.mkdir(parents=True, exist_ok=True)
        self.pretrained_path.mkdir(parents=True, exist_ok=True)

    def get_model_path(self, char_id: str) -> Path:
        """캐릭터 모델 디렉토리 경로"""
        return self.models_path / char_id

    def get_sovits_model_path(self, char_id: str) -> Path:
        """SoVITS 모델 파일 경로"""
        return self.get_model_path(char_id) / "sovits.pth"

    def get_gpt_model_path(self, char_id: str) -> Path:
        """GPT 모델 파일 경로"""
        return self.get_model_path(char_id) / "gpt.ckpt"

    def get_config_path(self, char_id: str) -> Path:
        """설정 파일 경로"""
        return self.get_model_path(char_id) / "config.json"

    def get_ref_audio_path(self, char_id: str) -> Path:
        """참조 오디오 경로"""
        return self.get_model_path(char_id) / "ref.wav"

    def get_ref_text_path(self, char_id: str) -> Path:
        """참조 오디오 텍스트 경로"""
        return self.get_model_path(char_id) / "ref.txt"
