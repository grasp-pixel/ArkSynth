"""GPT-SoVITS 모델 파일 관리"""

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

from .config import GPTSoVITSConfig

logger = logging.getLogger(__name__)


@dataclass
class ModelInfo:
    """학습된 모델 정보"""

    char_id: str
    char_name: str
    trained_at: str
    epochs_sovits: int
    epochs_gpt: int
    ref_audio_count: int
    language: str
    has_sovits: bool = False
    has_gpt: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> "ModelInfo":
        return cls(**data)

    def to_dict(self) -> dict:
        return asdict(self)


class GPTSoVITSModelManager:
    """GPT-SoVITS 모델 파일 관리자"""

    def __init__(self, config: GPTSoVITSConfig | None = None):
        self.config = config or GPTSoVITSConfig()
        self.config.ensure_directories()

    def is_trained(self, char_id: str) -> bool:
        """모델 준비 완료 여부 (학습 또는 zero-shot)"""
        # Zero-shot 모드: 참조 오디오 + 텍스트만 있으면 됨
        if self.is_zero_shot_ready(char_id):
            return True
        # 학습 모드: sovits.pth + gpt.ckpt 필요
        sovits_path = self.config.get_sovits_model_path(char_id)
        gpt_path = self.config.get_gpt_model_path(char_id)
        return sovits_path.exists() and gpt_path.exists()

    def is_zero_shot_ready(self, char_id: str) -> bool:
        """Zero-shot 합성 준비 여부 (참조 오디오만 필요)"""
        ref_audio = self.config.get_ref_audio_path(char_id)
        ref_text = self.config.get_ref_text_path(char_id)
        return ref_audio.exists() and ref_text.exists()

    def has_trained_model(self, char_id: str) -> bool:
        """전체 학습된 모델이 있는지 (zero-shot이 아닌)"""
        sovits_path = self.config.get_sovits_model_path(char_id)
        gpt_path = self.config.get_gpt_model_path(char_id)
        return sovits_path.exists() and gpt_path.exists()

    def get_trained_characters(self) -> list[str]:
        """준비 완료된 캐릭터 ID 목록 (학습 또는 zero-shot)"""
        if not self.config.models_path.exists():
            return []

        ready = []
        for model_dir in self.config.models_path.iterdir():
            if model_dir.is_dir() and model_dir.name != "pretrained":
                if self.is_trained(model_dir.name):
                    ready.append(model_dir.name)

        return sorted(ready)

    def get_model_info(self, char_id: str) -> ModelInfo | None:
        """모델 정보 조회"""
        config_path = self.config.get_config_path(char_id)
        if not config_path.exists():
            return None

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            info = ModelInfo.from_dict(data)
            # 파일 존재 여부 업데이트
            info.has_sovits = self.config.get_sovits_model_path(char_id).exists()
            info.has_gpt = self.config.get_gpt_model_path(char_id).exists()
            return info
        except Exception as e:
            logger.error(f"모델 정보 로드 실패 ({char_id}): {e}")
            return None

    def save_model_info(self, info: ModelInfo):
        """모델 정보 저장"""
        model_dir = self.config.get_model_path(info.char_id)
        model_dir.mkdir(parents=True, exist_ok=True)

        config_path = self.config.get_config_path(info.char_id)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(info.to_dict(), f, ensure_ascii=False, indent=2)

    def list_all_models(self) -> list[ModelInfo]:
        """모든 모델 정보 목록 (config.json 없어도 준비된 캐릭터 포함)"""
        models = []
        for char_id in self.get_trained_characters():
            info = self.get_model_info(char_id)
            if info:
                models.append(info)
            else:
                # config.json이 없어도 is_trained()가 True면 기본 정보 생성
                # (이전에 TTS 자동 준비로 ref.wav만 생성된 경우)
                model_dir = self.config.get_model_path(char_id)
                ref_count = len(list(model_dir.glob("ref*.wav"))) if model_dir.exists() else 0
                models.append(ModelInfo(
                    char_id=char_id,
                    char_name=char_id,  # 기본값으로 char_id 사용
                    trained_at=datetime.now().isoformat(),
                    epochs_sovits=0,
                    epochs_gpt=0,
                    ref_audio_count=ref_count,
                    language="ko",
                    has_sovits=self.config.get_sovits_model_path(char_id).exists(),
                    has_gpt=self.config.get_gpt_model_path(char_id).exists(),
                ))
        return models

    def delete_model(self, char_id: str) -> bool:
        """모델 삭제"""
        model_dir = self.config.get_model_path(char_id)
        if not model_dir.exists():
            return False

        try:
            import shutil

            shutil.rmtree(model_dir)
            logger.info(f"모델 삭제됨: {char_id}")
            return True
        except Exception as e:
            logger.error(f"모델 삭제 실패 ({char_id}): {e}")
            return False

    def get_sovits_path(self, char_id: str) -> Path | None:
        """SoVITS 모델 경로 (존재하는 경우)"""
        path = self.config.get_sovits_model_path(char_id)
        return path if path.exists() else None

    def get_gpt_path(self, char_id: str) -> Path | None:
        """GPT 모델 경로 (존재하는 경우)"""
        path = self.config.get_gpt_model_path(char_id)
        return path if path.exists() else None

    def create_model_info(
        self,
        char_id: str,
        char_name: str,
        epochs_sovits: int,
        epochs_gpt: int,
        ref_audio_count: int,
        language: str = "ko",
    ) -> ModelInfo:
        """새 모델 정보 생성 및 저장"""
        info = ModelInfo(
            char_id=char_id,
            char_name=char_name,
            trained_at=datetime.now().isoformat(),
            epochs_sovits=epochs_sovits,
            epochs_gpt=epochs_gpt,
            ref_audio_count=ref_audio_count,
            language=language,
            has_sovits=self.config.get_sovits_model_path(char_id).exists(),
            has_gpt=self.config.get_gpt_model_path(char_id).exists(),
        )
        self.save_model_info(info)
        return info
