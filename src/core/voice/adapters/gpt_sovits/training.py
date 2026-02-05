"""GPT-SoVITS 학습 어댑터

기존 GPTSoVITSTrainer를 래핑하여 TrainingAdapter 인터페이스 구현.
"""

import logging
from pathlib import Path
from typing import Callable

from ...interfaces import TrainingAdapter, TrainingConfig, TrainingMode, TrainingProgress
from ...gpt_sovits.config import GPTSoVITSConfig
from ...gpt_sovits.model_manager import GPTSoVITSModelManager
from ...gpt_sovits.trainer import GPTSoVITSTrainer
from ...gpt_sovits.trainer import TrainingProgress as LegacyTrainingProgress

logger = logging.getLogger(__name__)


class GPTSoVITSTrainingAdapter(TrainingAdapter):
    """GPT-SoVITS 학습 어댑터

    기존 GPTSoVITSTrainer를 래핑하여 TrainingAdapter 인터페이스 구현.
    """

    engine_name = "gpt_sovits"
    supported_modes = [TrainingMode.PREPARE, TrainingMode.FINETUNE]

    def __init__(
        self,
        config: GPTSoVITSConfig | None = None,
        model_manager: GPTSoVITSModelManager | None = None,
    ):
        self.config = config or GPTSoVITSConfig()
        self._model_manager = model_manager or GPTSoVITSModelManager(self.config)
        self._trainer = GPTSoVITSTrainer(self.config, self._model_manager)

    def get_default_config(self, mode: TrainingMode) -> dict:
        """기본 설정 반환"""
        if mode == TrainingMode.FINETUNE:
            return {
                "epochs_sovits": self.config.epochs_sovits,
                "epochs_gpt": self.config.epochs_gpt,
                "batch_size": self.config.batch_size,
            }
        # PREPARE 모드
        return {
            "ref_audio_count": self.config.ref_audio_count,
            "min_ref_audio_length": self.config.min_ref_audio_length,
            "max_ref_audio_length": self.config.max_ref_audio_length,
        }

    async def train(
        self,
        config: TrainingConfig,
        on_progress: Callable[[TrainingProgress], None] | None = None,
    ) -> bool:
        """학습 실행

        Args:
            config: 학습 설정
            on_progress: 진행 상황 콜백

        Returns:
            학습 성공 여부
        """
        # 콜백 변환 (새 인터페이스 -> 기존 인터페이스)
        def internal_callback(progress: LegacyTrainingProgress):
            if on_progress:
                on_progress(
                    TrainingProgress(
                        stage=progress.stage,
                        progress=progress.progress,
                        current_epoch=progress.current_epoch,
                        total_epochs=progress.total_epochs,
                        message=progress.message,
                    )
                )

        # 오디오 파일 목록
        audio_files = []
        if config.audio_dir.exists():
            audio_files = list(config.audio_dir.glob("*.mp3")) + list(config.audio_dir.glob("*.wav"))

        # 기존 trainer 호출
        return await self._trainer.train(
            char_id=config.char_id,
            char_name=config.char_name,
            audio_files=audio_files,
            mode=config.mode.value,  # TrainingMode -> str
            on_progress=internal_callback if on_progress else None,
        )

    def cancel(self) -> None:
        """학습 취소"""
        self._trainer.cancel()

    # 레거시 호환 프로퍼티
    @property
    def trainer(self) -> GPTSoVITSTrainer:
        """기존 trainer 접근 (레거시 호환)"""
        return self._trainer

    @property
    def model_manager(self) -> GPTSoVITSModelManager:
        """기존 model_manager 접근 (레거시 호환)"""
        return self._model_manager

    @property
    def last_error(self) -> str:
        """마지막 에러 메시지"""
        return self._trainer.last_error
