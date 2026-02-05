"""GPT-SoVITS 모델 관리 어댑터

기존 GPTSoVITSModelManager를 래핑하여 ModelAdapter 인터페이스 구현.
"""

import logging
from datetime import datetime
from pathlib import Path

from ...interfaces import ModelAdapter, ModelInfo, ModelType
from ...gpt_sovits.config import GPTSoVITSConfig
from ...gpt_sovits.model_manager import GPTSoVITSModelManager
from ...gpt_sovits.model_manager import ModelInfo as LegacyModelInfo

logger = logging.getLogger(__name__)


class GPTSoVITSModelAdapter(ModelAdapter):
    """GPT-SoVITS 모델 관리 어댑터

    기존 GPTSoVITSModelManager를 래핑하여 ModelAdapter 인터페이스 구현.
    """

    engine_name = "gpt_sovits"

    def __init__(
        self,
        config: GPTSoVITSConfig | None = None,
    ):
        self.config = config or GPTSoVITSConfig()
        self._manager = GPTSoVITSModelManager(self.config)
        self.models_path = self.config.models_path

    def get_model_type(self, char_id: str) -> ModelType:
        """모델 타입 조회"""
        type_str = self._manager.get_model_type(char_id)
        return ModelType(type_str)

    def is_ready(self, char_id: str) -> bool:
        """모델 사용 가능 여부"""
        return self._manager.is_trained(char_id)

    def list_models(self) -> list[ModelInfo]:
        """모든 모델 목록"""
        models = []
        for legacy_model in self._manager.list_all_models():
            model_type = self.get_model_type(legacy_model.char_id)

            # trained_at 파싱
            trained_at = None
            if legacy_model.trained_at:
                try:
                    trained_at = datetime.fromisoformat(legacy_model.trained_at)
                except ValueError:
                    pass

            models.append(
                ModelInfo(
                    char_id=legacy_model.char_id,
                    char_name=legacy_model.char_name,
                    model_type=model_type,
                    trained_at=trained_at,
                    language=legacy_model.language,
                    engine=self.engine_name,
                    extra_info={
                        "epochs_sovits": legacy_model.epochs_sovits,
                        "epochs_gpt": legacy_model.epochs_gpt,
                        "ref_audio_count": legacy_model.ref_audio_count,
                        "has_sovits": legacy_model.has_sovits,
                        "has_gpt": legacy_model.has_gpt,
                    },
                )
            )
        return models

    def delete_model(self, char_id: str) -> bool:
        """모델 삭제"""
        return self._manager.delete_model(char_id)

    # 레거시 호환 프로퍼티
    @property
    def manager(self) -> GPTSoVITSModelManager:
        """기존 model_manager 접근 (레거시 호환)"""
        return self._manager

    # 추가 유틸리티 메서드
    def is_zero_shot_ready(self, char_id: str) -> bool:
        """Zero-shot 준비 여부"""
        return self._manager.is_zero_shot_ready(char_id)

    def has_trained_model(self, char_id: str) -> bool:
        """학습된 모델 존재 여부"""
        return self._manager.has_trained_model(char_id)

    def get_trained_characters(self) -> list[str]:
        """준비된 캐릭터 ID 목록"""
        return self._manager.get_trained_characters()
