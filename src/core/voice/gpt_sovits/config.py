"""GPT-SoVITS 설정"""

import os
from dataclasses import dataclass, field
from pathlib import Path


# 기본 설치 경로 (앱 내 자동 설치 위치)
DEFAULT_INSTALL_BASE = Path("tools/gpt_sovits")
# 최신 통합 패키지 폴더명 (variant별)
INTEGRATED_FOLDERS = [
    "GPT-SoVITS-v2pro-20250604-nvidia50",  # RTX 50 전용 (우선)
    "GPT-SoVITS-v2pro-20250604",           # 표준
]
# 레거시 통합 패키지 경로
LEGACY_INTEGRATED_PATH = DEFAULT_INSTALL_BASE / "GPT-SoVITS-v2-240821"
# 소스 설치 경로 (레거시)
SOURCE_INSTALL_PATH = DEFAULT_INSTALL_BASE / "GPT-SoVITS-main"


def _get_default_gpt_sovits_path() -> Path:
    """GPT-SoVITS 기본 경로 결정

    우선순위:
    1. 환경변수 GPT_SOVITS_PATH
    2. 최신 통합 패키지 경로 (variant별 폴더 자동 탐색)
    3. 레거시 통합 패키지 경로 (tools/gpt_sovits/GPT-SoVITS-v2-240821)
    4. 소스 설치 경로 (tools/gpt_sovits/GPT-SoVITS-main)
    5. 레거시 경로 (C:/GPT-SoVITS)
    """
    # 환경변수 우선
    env_path = os.environ.get("GPT_SOVITS_PATH")
    if env_path:
        return Path(env_path)

    # 최신 통합 패키지 경로 확인 (variant별 폴더 자동 탐색)
    for folder in INTEGRATED_FOLDERS:
        path = DEFAULT_INSTALL_BASE / folder
        if path.exists():
            return path

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

    # 기본값 (표준 패키지가 설치될 경로)
    return DEFAULT_INSTALL_BASE / INTEGRATED_FOLDERS[-1]


def _get_project_root() -> Path:
    """프로젝트 루트 디렉토리 찾기 (pyproject.toml 기준)"""
    # config.py 위치에서 시작
    current = Path(__file__).parent
    for _ in range(10):  # 최대 10단계까지 탐색
        if (current / "pyproject.toml").exists():
            return current
        parent = current.parent
        if parent == current:  # 루트 도달
            break
        current = parent
    # 찾지 못하면 CWD 사용
    return Path.cwd()


# 프로젝트 루트 캐시
_PROJECT_ROOT: Path | None = None


def get_project_root() -> Path:
    """프로젝트 루트 반환 (캐시됨)"""
    global _PROJECT_ROOT
    if _PROJECT_ROOT is None:
        _PROJECT_ROOT = _get_project_root()
    return _PROJECT_ROOT


@dataclass
class GPTSoVITSConfig:
    """GPT-SoVITS 학습 및 추론 설정"""

    # GPT-SoVITS 설치 경로
    gpt_sovits_path: Path = field(default_factory=_get_default_gpt_sovits_path)

    # API 서버 설정
    api_host: str = "127.0.0.1"
    api_port: int = 9880

    # 경로 설정
    models_path: Path = field(default_factory=lambda: Path("models/gpt_sovits"))
    extracted_path: Path = field(default_factory=lambda: Path("extracted"))
    pretrained_path: Path = field(
        default_factory=lambda: Path("models/gpt_sovits/pretrained")
    )

    def __post_init__(self):
        """상대 경로를 프로젝트 루트 기준 절대 경로로 변환"""
        root = get_project_root()

        # 상대 경로인 경우 프로젝트 루트 기준으로 절대 경로 변환
        if not self.gpt_sovits_path.is_absolute():
            self.gpt_sovits_path = (root / self.gpt_sovits_path).resolve()
        if not self.models_path.is_absolute():
            self.models_path = (root / self.models_path).resolve()
        if not self.extracted_path.is_absolute():
            self.extracted_path = (root / self.extracted_path).resolve()
        if not self.pretrained_path.is_absolute():
            self.pretrained_path = (root / self.pretrained_path).resolve()

    # 학습 설정
    epochs_sovits: int = 12  # SoVITS 학습 에포크 (과적합 시 기계음 발생, 8~12 권장)
    epochs_gpt: int = 15  # GPT 학습 에포크 (소량 데이터 시 15~20 권장)
    batch_size: int = 4
    learning_rate: float = 0.0001

    # 오디오 설정
    sample_rate: int = 32000  # GPT-SoVITS 기본
    hop_length: int = 640
    win_length: int = 2048

    # TTS 추론 설정
    # 이 값들은 백엔드에서 사용되며, 프론트엔드에서는 기본값만 사용
    speed_factor: float = 1.0  # 음성 속도 (0.5~2.0, 1.0=기본)
    top_k: int = 12  # 샘플링 다양성 (5~15 권장)
    top_p: float = 1.0  # Nucleus sampling (0.1~1.0)
    temperature: float = 0.8  # 음성 랜덤성 (0.6~1.0, 낮을수록 안정)

    # 언어 설정 (한국어 우선)
    default_language: str = "ko"

    # 참조 오디오 설정
    min_ref_audio_length: float = 3.0  # 최소 참조 오디오 길이 (초)
    max_ref_audio_length: float = (
        10.0  # 최대 참조 오디오 길이 (초) - 너무 긴 오디오는 품질 저하
    )
    ref_audio_count: int = 5  # 학습에 사용할 참조 오디오 개수

    # Whisper 전처리 설정 (학습 데이터 준비용)
    whisper_model_size: str = "large-v3-turbo"  # Whisper 모델 크기
    whisper_compute_type: str = "float16"  # 연산 타입 (float16, int8, float32)
    use_whisper_preprocessing: bool = True  # Whisper 기반 전처리 사용 여부

    # 학습 후 정리 설정
    cleanup_after_training: bool = True  # 학습 완료 후 training_data 폴더 자동 삭제

    @property
    def api_url(self) -> str:
        """GPT-SoVITS API 서버 URL"""
        return f"http://{self.api_host}:{self.api_port}"

    @property
    def is_gpt_sovits_installed(self) -> bool:
        """GPT-SoVITS 설치 여부 확인"""
        # api_v2.py 또는 api.py 존재 확인
        return (self.gpt_sovits_path / "api_v2.py").exists() or (
            self.gpt_sovits_path / "api.py"
        ).exists()

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

    def _resolve_lang(self, lang: str | None) -> str:
        """lang이 None이면 default_language 사용"""
        return lang or self.default_language

    def get_lang_models_path(self, lang: str | None = None) -> Path:
        """언어별 모델 루트 경로 (models/gpt_sovits/{lang}/)"""
        return self.models_path / self._resolve_lang(lang)

    def get_model_path(self, char_id: str, lang: str | None = None) -> Path:
        """캐릭터 모델 디렉토리 경로 (models/gpt_sovits/{lang}/{char_id}/)"""
        return self.get_lang_models_path(lang) / char_id

    def get_sovits_model_path(self, char_id: str, lang: str | None = None) -> Path:
        """SoVITS 모델 파일 경로"""
        return self.get_model_path(char_id, lang) / "sovits.pth"

    def get_gpt_model_path(self, char_id: str, lang: str | None = None) -> Path:
        """GPT 모델 파일 경로"""
        return self.get_model_path(char_id, lang) / "gpt.ckpt"

    def get_config_path(self, char_id: str, lang: str | None = None) -> Path:
        """설정 파일 경로"""
        return self.get_model_path(char_id, lang) / "config.json"

    def get_ref_audio_path(self, char_id: str, lang: str | None = None) -> Path:
        """참조 오디오 경로 (DEPRECATED - 레거시 호환용)"""
        return self.get_model_path(char_id, lang) / "ref.wav"

    def get_ref_text_path(self, char_id: str, lang: str | None = None) -> Path:
        """참조 오디오 텍스트 경로 (DEPRECATED - 레거시 호환용)"""
        return self.get_model_path(char_id, lang) / "ref.txt"

    def get_training_data_path(self, char_id: str, lang: str | None = None) -> Path:
        """Fine-tuning 학습 데이터 경로"""
        return self.get_model_path(char_id, lang) / "training_data"

    def get_sliced_audio_path(self, char_id: str, lang: str | None = None) -> Path:
        """슬라이싱된 오디오 경로 (레거시)"""
        return self.get_training_data_path(char_id, lang) / "sliced"

    def get_preprocessed_audio_path(self, char_id: str, lang: str | None = None) -> Path:
        """Whisper 전처리된 오디오 경로"""
        return self.get_model_path(char_id, lang) / "preprocessed"

    def get_preprocessed_segments_path(self, char_id: str, lang: str | None = None) -> Path:
        """전처리된 세그먼트 정보 파일 경로 (DEPRECATED)"""
        return self.get_preprocessed_audio_path(char_id, lang) / "segments.json"

    def get_training_list_path(self, char_id: str, lang: str | None = None) -> Path:
        """학습용 .list 파일 경로"""
        return self.get_training_data_path(char_id, lang) / "train.list"
