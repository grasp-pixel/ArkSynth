"""GPT-SoVITS 학습 로직

GPT-SoVITS를 사용한 캐릭터 음성 모델 학습.
실제 학습은 GPT-SoVITS 라이브러리를 호출하여 수행.
"""

import asyncio
import logging
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .config import GPTSoVITSConfig
from .model_manager import GPTSoVITSModelManager

logger = logging.getLogger(__name__)


@dataclass
class TrainingProgress:
    """학습 진행 상황"""

    stage: str  # preprocessing, sovits_training, gpt_training, complete
    progress: float  # 0.0 ~ 1.0
    current_epoch: int = 0
    total_epochs: int = 0
    message: str = ""


class GPTSoVITSTrainer:
    """GPT-SoVITS 모델 학습기

    학습 단계:
    1. 오디오 전처리 (리샘플링, 노이즈 제거)
    2. 참조 오디오 선택
    3. SoVITS 모델 fine-tuning
    4. GPT 모델 fine-tuning
    """

    def __init__(
        self,
        config: GPTSoVITSConfig | None = None,
        model_manager: GPTSoVITSModelManager | None = None,
    ):
        self.config = config or GPTSoVITSConfig()
        self.model_manager = model_manager or GPTSoVITSModelManager(self.config)
        self._cancelled = False

    def cancel(self):
        """학습 취소"""
        self._cancelled = True

    async def train(
        self,
        char_id: str,
        char_name: str,
        audio_files: list[Path],
        on_progress: Callable[[TrainingProgress], None] | None = None,
    ) -> bool:
        """캐릭터 음성 모델 학습

        Args:
            char_id: 캐릭터 ID
            char_name: 캐릭터 이름
            audio_files: 학습용 오디오 파일 목록
            on_progress: 진행 상황 콜백

        Returns:
            bool: 학습 성공 여부
        """
        self._cancelled = False

        try:
            # 1. 전처리
            if on_progress:
                on_progress(
                    TrainingProgress(
                        stage="preprocessing",
                        progress=0.0,
                        message=f"{char_name} 오디오 전처리 중...",
                    )
                )

            if self._cancelled:
                return False

            # 참조 오디오 선택 및 전처리
            ref_audios = await self._prepare_reference_audios(audio_files)
            if not ref_audios:
                logger.error(f"참조 오디오 준비 실패: {char_id}")
                return False

            if on_progress:
                on_progress(
                    TrainingProgress(
                        stage="preprocessing",
                        progress=0.2,
                        message=f"참조 오디오 {len(ref_audios)}개 준비 완료",
                    )
                )

            if self._cancelled:
                return False

            # 2. SoVITS 학습
            if on_progress:
                on_progress(
                    TrainingProgress(
                        stage="sovits_training",
                        progress=0.3,
                        current_epoch=0,
                        total_epochs=self.config.epochs_sovits,
                        message="SoVITS 모델 학습 시작...",
                    )
                )

            sovits_success = await self._train_sovits(
                char_id, ref_audios, on_progress
            )
            if not sovits_success:
                logger.error(f"SoVITS 학습 실패: {char_id}")
                return False

            if self._cancelled:
                return False

            # 3. GPT 학습
            if on_progress:
                on_progress(
                    TrainingProgress(
                        stage="gpt_training",
                        progress=0.6,
                        current_epoch=0,
                        total_epochs=self.config.epochs_gpt,
                        message="GPT 모델 학습 시작...",
                    )
                )

            gpt_success = await self._train_gpt(char_id, ref_audios, on_progress)
            if not gpt_success:
                logger.error(f"GPT 학습 실패: {char_id}")
                return False

            # 4. 모델 정보 저장
            self.model_manager.create_model_info(
                char_id=char_id,
                char_name=char_name,
                epochs_sovits=self.config.epochs_sovits,
                epochs_gpt=self.config.epochs_gpt,
                ref_audio_count=len(ref_audios),
                language=self.config.default_language,
            )

            if on_progress:
                on_progress(
                    TrainingProgress(
                        stage="complete",
                        progress=1.0,
                        message=f"{char_name} 학습 완료!",
                    )
                )

            logger.info(f"학습 완료: {char_id} ({char_name})")
            return True

        except Exception as e:
            logger.error(f"학습 중 오류 ({char_id}): {e}")
            return False

    async def _prepare_reference_audios(
        self, audio_files: list[Path]
    ) -> list[Path]:
        """참조 오디오 준비 (전처리)

        Args:
            audio_files: 원본 오디오 파일 목록

        Returns:
            전처리된 참조 오디오 경로 목록
        """
        # TODO: 실제 구현 시 오디오 전처리 로직 추가
        # - 리샘플링 (32kHz)
        # - 노이즈 제거
        # - 적절한 길이의 오디오 선택

        # 현재는 원본 파일 중 일부 선택
        selected = audio_files[: self.config.ref_audio_count]
        return selected

    async def _train_sovits(
        self,
        char_id: str,
        ref_audios: list[Path],
        on_progress: Callable[[TrainingProgress], None] | None = None,
    ) -> bool:
        """SoVITS 모델 학습

        TODO: 실제 GPT-SoVITS 라이브러리 연동 필요
        현재는 모델 파일 생성 시뮬레이션
        """
        model_dir = self.config.get_model_path(char_id)
        model_dir.mkdir(parents=True, exist_ok=True)

        # 학습 시뮬레이션 (실제 구현 시 GPT-SoVITS 호출)
        for epoch in range(self.config.epochs_sovits):
            if self._cancelled:
                return False

            await asyncio.sleep(0.5)  # 시뮬레이션용 딜레이 (진행 상황 확인용)

            if on_progress:
                progress = 0.3 + (0.3 * (epoch + 1) / self.config.epochs_sovits)
                on_progress(
                    TrainingProgress(
                        stage="sovits_training",
                        progress=progress,
                        current_epoch=epoch + 1,
                        total_epochs=self.config.epochs_sovits,
                        message=f"SoVITS Epoch {epoch + 1}/{self.config.epochs_sovits}",
                    )
                )
                logger.info(f"[Train] SoVITS {epoch + 1}/{self.config.epochs_sovits}")

        # 모델 파일 생성 (플레이스홀더)
        sovits_path = self.config.get_sovits_model_path(char_id)
        sovits_path.write_text(f"sovits_model_placeholder_{char_id}")

        return True

    async def _train_gpt(
        self,
        char_id: str,
        ref_audios: list[Path],
        on_progress: Callable[[TrainingProgress], None] | None = None,
    ) -> bool:
        """GPT 모델 학습

        TODO: 실제 GPT-SoVITS 라이브러리 연동 필요
        현재는 모델 파일 생성 시뮬레이션
        """
        # 학습 시뮬레이션
        for epoch in range(self.config.epochs_gpt):
            if self._cancelled:
                return False

            await asyncio.sleep(0.5)  # 시뮬레이션용 딜레이 (진행 상황 확인용)

            if on_progress:
                progress = 0.6 + (0.35 * (epoch + 1) / self.config.epochs_gpt)
                on_progress(
                    TrainingProgress(
                        stage="gpt_training",
                        progress=progress,
                        current_epoch=epoch + 1,
                        total_epochs=self.config.epochs_gpt,
                        message=f"GPT Epoch {epoch + 1}/{self.config.epochs_gpt}",
                    )
                )
                logger.info(f"[Train] GPT {epoch + 1}/{self.config.epochs_gpt}")

        # 모델 파일 생성 (플레이스홀더)
        gpt_path = self.config.get_gpt_model_path(char_id)
        gpt_path.write_text(f"gpt_model_placeholder_{char_id}")

        return True
