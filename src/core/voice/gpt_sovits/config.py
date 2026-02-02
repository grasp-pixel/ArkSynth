"""GPT-SoVITS 설정"""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class GPTSoVITSConfig:
    """GPT-SoVITS 학습 및 추론 설정"""

    # 경로 설정
    models_path: Path = field(default_factory=lambda: Path("models/gpt_sovits"))
    extracted_path: Path = field(default_factory=lambda: Path("extracted/voice"))
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
    max_ref_audio_length: float = 10.0  # 최대 참조 오디오 길이 (초)
    ref_audio_count: int = 5  # 학습에 사용할 참조 오디오 개수

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
