"""GPT-SoVITS 학습 작업 관리"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable

from .config import GPTSoVITSConfig
from .model_manager import GPTSoVITSModelManager
from .trainer import GPTSoVITSTrainer, TrainingProgress

logger = logging.getLogger(__name__)


class TrainingStatus(str, Enum):
    """학습 상태"""

    PENDING = "pending"
    PREPROCESSING = "preprocessing"
    TRAINING = "training"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TrainingJob:
    """학습 작업 정보"""

    job_id: str
    char_id: str
    char_name: str
    status: TrainingStatus = TrainingStatus.PENDING
    progress: float = 0.0
    current_epoch: int = 0
    total_epochs: int = 0
    message: str = ""
    error_message: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: datetime | None = None
    completed_at: datetime | None = None

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "char_id": self.char_id,
            "char_name": self.char_name,
            "status": self.status.value,
            "progress": self.progress,
            "current_epoch": self.current_epoch,
            "total_epochs": self.total_epochs,
            "message": self.message,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class TrainingManager:
    """학습 작업 큐 관리자

    특징:
    - 하나의 학습만 동시 실행 (GPU 메모리 제약)
    - 작업 큐로 순차 처리
    - 진행 상황 콜백 지원
    """

    def __init__(
        self,
        config: GPTSoVITSConfig | None = None,
        model_manager: GPTSoVITSModelManager | None = None,
    ):
        self.config = config or GPTSoVITSConfig()
        self.model_manager = model_manager or GPTSoVITSModelManager(self.config)
        self.trainer = GPTSoVITSTrainer(self.config, self.model_manager)

        self._queue: asyncio.Queue[TrainingJob] = asyncio.Queue()
        self._jobs: dict[str, TrainingJob] = {}
        self._current_job: TrainingJob | None = None
        self._is_running = False
        self._worker_task: asyncio.Task | None = None
        self._progress_callbacks: list[Callable[[TrainingJob], None]] = []

    def add_progress_callback(self, callback: Callable[[TrainingJob], None]):
        """진행 상황 콜백 등록"""
        self._progress_callbacks.append(callback)

    def remove_progress_callback(self, callback: Callable[[TrainingJob], None]):
        """진행 상황 콜백 제거"""
        if callback in self._progress_callbacks:
            self._progress_callbacks.remove(callback)

    def _notify_progress(self, job: TrainingJob):
        """진행 상황 알림"""
        for callback in self._progress_callbacks:
            try:
                callback(job)
            except Exception as e:
                logger.error(f"Progress callback error: {e}")

    async def start(self):
        """작업 워커 시작"""
        if self._is_running:
            return

        self._is_running = True
        self._worker_task = asyncio.create_task(self._worker())
        logger.info("Training manager started")

    async def stop(self):
        """작업 워커 중지"""
        self._is_running = False

        if self._current_job:
            self.trainer.cancel()

        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

        logger.info("Training manager stopped")

    async def _worker(self):
        """작업 처리 워커"""
        while self._is_running:
            try:
                # 큐에서 작업 가져오기 (타임아웃 1초)
                try:
                    job = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue

                self._current_job = job
                job.status = TrainingStatus.PREPROCESSING
                job.started_at = datetime.now()
                self._notify_progress(job)

                # 오디오 파일 가져오기
                audio_files = self._get_audio_files(job.char_id)
                if not audio_files:
                    job.status = TrainingStatus.FAILED
                    job.error_message = "오디오 파일을 찾을 수 없습니다"
                    job.completed_at = datetime.now()
                    self._notify_progress(job)
                    self._current_job = None
                    continue

                # 학습 실행
                job.status = TrainingStatus.TRAINING

                def on_progress(progress: TrainingProgress):
                    job.progress = progress.progress
                    job.current_epoch = progress.current_epoch
                    job.total_epochs = progress.total_epochs
                    job.message = progress.message
                    self._notify_progress(job)

                success = await self.trainer.train(
                    char_id=job.char_id,
                    char_name=job.char_name,
                    audio_files=audio_files,
                    on_progress=on_progress,
                )

                if success:
                    job.status = TrainingStatus.COMPLETED
                    job.progress = 1.0
                    job.message = "학습 완료"
                else:
                    if self.trainer._cancelled:
                        job.status = TrainingStatus.CANCELLED
                        job.message = "학습 취소됨"
                    else:
                        job.status = TrainingStatus.FAILED
                        job.error_message = self.trainer.last_error or "학습 실패"

                job.completed_at = datetime.now()
                self._notify_progress(job)
                self._current_job = None

            except Exception as e:
                logger.error(f"Worker error: {e}")
                if self._current_job:
                    self._current_job.status = TrainingStatus.FAILED
                    self._current_job.error_message = str(e)
                    self._current_job.completed_at = datetime.now()
                    self._notify_progress(self._current_job)
                    self._current_job = None

    def _get_audio_files(self, char_id: str) -> list[Path]:
        """캐릭터 오디오 파일 목록"""
        audio_dir = self.config.extracted_path / char_id
        if not audio_dir.exists():
            return []

        files = []
        for ext in ["*.mp3", "*.wav", "*.ogg"]:
            files.extend(audio_dir.glob(ext))

        return sorted(files)

    async def queue_training(
        self, char_id: str, char_name: str
    ) -> TrainingJob:
        """학습 작업 큐에 추가

        Args:
            char_id: 캐릭터 ID
            char_name: 캐릭터 이름

        Returns:
            생성된 TrainingJob
        """
        job = TrainingJob(
            job_id=str(uuid.uuid4())[:8],
            char_id=char_id,
            char_name=char_name,
            total_epochs=self.config.epochs_sovits + self.config.epochs_gpt,
        )

        self._jobs[job.job_id] = job
        await self._queue.put(job)

        logger.info(f"Training queued: {char_id} ({char_name})")
        return job

    async def queue_batch_training(
        self, characters: list[tuple[str, str]]
    ) -> list[TrainingJob]:
        """여러 캐릭터 일괄 학습 큐 추가

        Args:
            characters: (char_id, char_name) 튜플 목록

        Returns:
            생성된 TrainingJob 목록
        """
        jobs = []
        for char_id, char_name in characters:
            # 이미 학습된 캐릭터는 건너뛰기
            if self.model_manager.is_trained(char_id):
                logger.info(f"이미 학습됨, 건너뛰기: {char_id}")
                continue

            job = await self.queue_training(char_id, char_name)
            jobs.append(job)

        return jobs

    def get_job(self, job_id: str) -> TrainingJob | None:
        """작업 조회"""
        return self._jobs.get(job_id)

    def get_all_jobs(self) -> list[TrainingJob]:
        """모든 작업 목록"""
        return list(self._jobs.values())

    def get_pending_jobs(self) -> list[TrainingJob]:
        """대기 중인 작업 목록"""
        return [j for j in self._jobs.values() if j.status == TrainingStatus.PENDING]

    def get_current_job(self) -> TrainingJob | None:
        """현재 진행 중인 작업"""
        return self._current_job

    async def cancel_job(self, job_id: str) -> bool:
        """작업 취소"""
        job = self._jobs.get(job_id)
        if not job:
            return False

        if job.status == TrainingStatus.PENDING:
            # 대기 중인 작업은 상태만 변경
            job.status = TrainingStatus.CANCELLED
            job.completed_at = datetime.now()
            self._notify_progress(job)
            return True

        if job == self._current_job:
            # 진행 중인 작업은 trainer 취소
            self.trainer.cancel()
            return True

        return False

    def get_status_summary(self) -> dict:
        """전체 상태 요약"""
        total_trained = len(self.model_manager.get_trained_characters())
        pending_count = len(self.get_pending_jobs())

        return {
            "is_training": self._current_job is not None,
            "current_job": self._current_job.to_dict() if self._current_job else None,
            "queue_length": pending_count,
            "trained_count": total_trained,
        }
