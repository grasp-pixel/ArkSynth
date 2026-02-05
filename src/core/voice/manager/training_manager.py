"""통합 학습 매니저

여러 TTS 엔진의 학습 기능을 통합 관리.
기존 TrainingManager를 래핑하고 엔진 선택 기능 추가.
"""

import logging
from typing import Literal

from ..interfaces import TrainingAdapter, TrainingConfig, TrainingMode, TrainingProgress
from ..adapters.gpt_sovits import GPTSoVITSTrainingAdapter, GPTSoVITSModelAdapter
from ..gpt_sovits.training_manager import TrainingManager, TrainingJob, TrainingStatus
from ..gpt_sovits.config import GPTSoVITSConfig
from ..gpt_sovits.model_manager import GPTSoVITSModelManager

logger = logging.getLogger(__name__)

EngineType = Literal["gpt_sovits", "qwen3_tts"]


class UnifiedTrainingManager:
    """통합 학습 매니저

    여러 TTS 엔진의 학습 기능을 통합 관리합니다.
    기존 TrainingManager를 래핑하고 엔진 선택 기능을 추가합니다.
    """

    def __init__(self):
        self._adapters: dict[str, TrainingAdapter] = {}
        self._model_adapters: dict[str, GPTSoVITSModelAdapter] = {}
        self._managers: dict[str, TrainingManager] = {}
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """초기화 (lazy)"""
        if self._initialized:
            return

        # GPT-SoVITS 초기화
        try:
            gpt_config = GPTSoVITSConfig()
            gpt_model_manager = GPTSoVITSModelManager(gpt_config)

            # 기존 TrainingManager (작업 큐 관리용)
            self._managers["gpt_sovits"] = TrainingManager(gpt_config, gpt_model_manager)

            # 어댑터
            self._adapters["gpt_sovits"] = GPTSoVITSTrainingAdapter(gpt_config, gpt_model_manager)
            self._model_adapters["gpt_sovits"] = GPTSoVITSModelAdapter(gpt_config)

            logger.info("GPT-SoVITS 학습 매니저 초기화 완료")
        except Exception as e:
            logger.error(f"GPT-SoVITS 학습 매니저 초기화 실패: {e}")

        # Qwen3-TTS는 현재 미구현
        # 실제 구현 시 추가

        self._initialized = True

    def get_manager(self, engine: EngineType = "gpt_sovits") -> TrainingManager | None:
        """특정 엔진의 TrainingManager 반환 (레거시 호환)

        Args:
            engine: 엔진 이름

        Returns:
            TrainingManager 또는 None
        """
        self._ensure_initialized()
        return self._managers.get(engine)

    def get_adapter(self, engine: EngineType = "gpt_sovits") -> TrainingAdapter | None:
        """특정 엔진의 TrainingAdapter 반환

        Args:
            engine: 엔진 이름

        Returns:
            TrainingAdapter 또는 None
        """
        self._ensure_initialized()
        return self._adapters.get(engine)

    def get_model_adapter(self, engine: EngineType = "gpt_sovits") -> GPTSoVITSModelAdapter | None:
        """특정 엔진의 ModelAdapter 반환

        Args:
            engine: 엔진 이름

        Returns:
            ModelAdapter 또는 None
        """
        self._ensure_initialized()
        return self._model_adapters.get(engine)

    async def queue_training(
        self,
        char_id: str,
        char_name: str,
        mode: str = "prepare",
        engine: EngineType = "gpt_sovits",
    ) -> TrainingJob:
        """학습 작업 큐에 추가

        Args:
            char_id: 캐릭터 ID
            char_name: 캐릭터 이름
            mode: 학습 모드 ("prepare" 또는 "finetune")
            engine: 엔진 이름

        Returns:
            TrainingJob 객체
        """
        self._ensure_initialized()

        manager = self._managers.get(engine)
        if not manager:
            raise ValueError(f"지원하지 않는 엔진: {engine}")

        return await manager.queue_training(char_id, char_name, mode)

    # 기존 TrainingManager 메서드 위임
    def get_job(self, job_id: str, engine: EngineType = "gpt_sovits") -> TrainingJob | None:
        """학습 작업 조회"""
        self._ensure_initialized()
        manager = self._managers.get(engine)
        return manager.get_job(job_id) if manager else None

    def get_all_jobs(self, engine: EngineType = "gpt_sovits") -> list[TrainingJob]:
        """모든 학습 작업 조회"""
        self._ensure_initialized()
        manager = self._managers.get(engine)
        return manager.get_all_jobs() if manager else []

    def cancel_job(self, job_id: str, engine: EngineType = "gpt_sovits") -> bool:
        """학습 작업 취소"""
        self._ensure_initialized()
        manager = self._managers.get(engine)
        if manager:
            return manager.cancel_job(job_id)
        return False

    def get_status_summary(self, engine: EngineType = "gpt_sovits") -> dict:
        """학습 상태 요약"""
        self._ensure_initialized()
        manager = self._managers.get(engine)
        if manager:
            return manager.get_status_summary()
        return {
            "total_jobs": 0,
            "pending": 0,
            "running": 0,
            "completed": 0,
            "failed": 0,
        }

    def get_available_engines(self) -> list[str]:
        """사용 가능한 엔진 목록"""
        self._ensure_initialized()
        return list(self._managers.keys())


# 싱글톤 인스턴스
_unified_training_manager: UnifiedTrainingManager | None = None


def get_unified_training_manager() -> UnifiedTrainingManager:
    """통합 학습 매니저 싱글톤 인스턴스 반환"""
    global _unified_training_manager
    if _unified_training_manager is None:
        _unified_training_manager = UnifiedTrainingManager()
    return _unified_training_manager
