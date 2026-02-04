"""백그라운드 렌더링 관리자"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable, Any

from .render_cache import RenderCache, get_render_cache
from ..backend import gpu_semaphore_context
from ..voice.alias_resolver import resolve_voice_char_id

logger = logging.getLogger(__name__)


class RenderStatus(str, Enum):
    """렌더링 상태"""

    IDLE = "idle"
    RENDERING = "rendering"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass
class RenderProgress:
    """렌더링 진행 상태"""

    episode_id: str
    status: RenderStatus
    total: int
    completed: int
    current_index: int | None = None
    current_text: str | None = None
    error: str | None = None
    started_at: str | None = None
    finished_at: str | None = None

    @property
    def progress_percent(self) -> float:
        if self.total == 0:
            return 0.0
        return (self.completed / self.total) * 100


@dataclass
class RenderJob:
    """렌더링 작업"""

    episode_id: str
    dialogues: list[dict]  # {index, char_id, text}
    language: str = "ko"
    default_char_id: str | None = None  # 모델 없는 캐릭터용 기본 음성
    narrator_char_id: str | None = None  # 나레이션용 캐릭터
    speaker_voice_map: dict[str, str] = field(default_factory=dict)  # 화자별 음성 매핑
    priority: int = 0


class RenderManager:
    """백그라운드 렌더링 관리자

    에피소드 대사들을 백그라운드에서 순차적으로 렌더링합니다.
    """

    def __init__(self, cache: RenderCache | None = None):
        self.cache = cache or get_render_cache()
        self._current_job: RenderJob | None = None
        self._progress: RenderProgress | None = None
        self._cancel_requested = False
        self._task: asyncio.Task | None = None
        self._progress_callbacks: list[Callable[[RenderProgress], Any]] = []

    @property
    def is_rendering(self) -> bool:
        return self._task is not None and not self._task.done()

    @property
    def current_episode_id(self) -> str | None:
        return self._current_job.episode_id if self._current_job else None

    def get_progress(self, episode_id: str | None = None) -> RenderProgress | None:
        """진행 상태 조회"""
        if episode_id is None:
            return self._progress

        if self._progress and self._progress.episode_id == episode_id:
            return self._progress

        # 캐시에서 완료된 상태 확인
        if self.cache.has_cache(episode_id):
            completed, total = self.cache.get_progress(episode_id)
            status = (
                RenderStatus.COMPLETED if completed >= total else RenderStatus.IDLE
            )
            return RenderProgress(
                episode_id=episode_id,
                status=status,
                total=total,
                completed=completed,
            )

        return None

    def add_progress_callback(self, callback: Callable[[RenderProgress], Any]):
        """진행률 콜백 등록"""
        self._progress_callbacks.append(callback)

    def remove_progress_callback(self, callback: Callable[[RenderProgress], Any]):
        """진행률 콜백 제거"""
        if callback in self._progress_callbacks:
            self._progress_callbacks.remove(callback)

    async def _notify_progress(self):
        """진행률 콜백 호출"""
        if self._progress:
            for callback in self._progress_callbacks:
                try:
                    result = callback(self._progress)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as e:
                    logger.error(f"진행률 콜백 오류: {e}")

    async def start_render(
        self,
        episode_id: str,
        dialogues: list[dict],
        language: str = "ko",
        default_char_id: str | None = None,
        narrator_char_id: str | None = None,
        speaker_voice_map: dict[str, str] | None = None,
        force: bool = False,
    ) -> RenderProgress:
        """렌더링 시작

        Args:
            episode_id: 에피소드 ID
            dialogues: 대사 목록 [{index, char_id, text}, ...]
            language: 언어 코드
            default_char_id: 모델 없는 캐릭터용 기본 음성
            narrator_char_id: 나레이션용 캐릭터
            speaker_voice_map: 화자별 음성 매핑 {char_id: voice_char_id}
            force: 기존 캐시 무시하고 다시 렌더링

        Returns:
            RenderProgress
        """
        if self.is_rendering:
            if self.current_episode_id == episode_id:
                return self._progress  # type: ignore
            raise ValueError(f"이미 렌더링 중: {self.current_episode_id}")

        # force=True이면 기존 캐시 삭제
        if force and self.cache.has_cache(episode_id):
            logger.info(f"기존 캐시 삭제 (force): {episode_id}")
            self.cache.delete_cache(episode_id)

        # 이미 완료된 캐시 확인
        if self.cache.is_complete(episode_id):
            logger.info(f"이미 렌더링 완료: {episode_id}")
            completed, total = self.cache.get_progress(episode_id)
            return RenderProgress(
                episode_id=episode_id,
                status=RenderStatus.COMPLETED,
                total=total,
                completed=completed,
            )

        # 작업 생성
        self._current_job = RenderJob(
            episode_id=episode_id,
            dialogues=dialogues,
            language=language,
            default_char_id=default_char_id,
            narrator_char_id=narrator_char_id,
            speaker_voice_map=speaker_voice_map or {},
        )

        # 진행 상태 초기화
        self._progress = RenderProgress(
            episode_id=episode_id,
            status=RenderStatus.RENDERING,
            total=len(dialogues),
            completed=0,
            started_at=datetime.now().isoformat(),
        )

        self._cancel_requested = False

        # 백그라운드 태스크 시작
        self._task = asyncio.create_task(self._render_task())

        await self._notify_progress()
        return self._progress

    async def cancel_render(self, episode_id: str | None = None) -> bool:
        """렌더링 취소"""
        if not self.is_rendering:
            return False

        if episode_id and self.current_episode_id != episode_id:
            return False

        self._cancel_requested = True
        logger.info(f"렌더링 취소 요청: {self.current_episode_id}")
        return True

    async def _render_task(self):
        """백그라운드 렌더링 태스크"""
        if not self._current_job or not self._progress:
            return

        job = self._current_job
        episode_id = job.episode_id

        try:
            # 합성기 가져오기 (config 참조 위해 먼저 로드)
            from ..voice.gpt_sovits import get_synthesizer

            synthesizer = get_synthesizer()

            # 백엔드 config에서 언어 설정 가져오기 (실시간 TTS와 동일)
            from ..backend.config import config as app_config
            gpt_language = app_config.gpt_sovits_language

            # 메타데이터 생성 또는 로드
            meta = self.cache.get_meta(episode_id)
            if meta is None:
                meta = self.cache.create_meta(
                    episode_id, len(job.dialogues), gpt_language
                )

            # 이미 렌더링된 인덱스
            rendered_indices = {a.index for a in meta.audios}
            self._progress.completed = len(rendered_indices)

            # 대사별 렌더링
            logger.info(f"[RenderManager] 렌더링 시작 - episode: {episode_id}, total dialogues: {len(job.dialogues)}")
            if job.dialogues:
                first = job.dialogues[0]
                logger.info(f"[RenderManager] 첫 번째 대사: [{first.get('char_id')}] {first['text'][:50]}...")

            # 자동 준비 헬퍼 함수
            from ..voice.gpt_sovits.training_worker import prepare_reference_audio
            from ..backend.config import config

            async def ensure_char_ready(cid: str) -> bool:
                """캐릭터 음성 준비 확인 및 자동 준비"""
                if await synthesizer.is_available(cid):
                    return True
                # 음성 파일이 있으면 자동 준비 시도
                audio_dir = config.extracted_path / cid
                if audio_dir.exists():
                    logger.info(f"[RenderManager] 캐릭터 자동 준비 시도: {cid}")
                    output_dir = config.models_path / "gpt_sovits" / cid
                    gamedata_path = Path("data/gamedata_yostar")
                    success = prepare_reference_audio(
                        char_id=cid,
                        audio_dir=audio_dir,
                        output_dir=output_dir,
                        gamedata_path=gamedata_path,
                        language=config.gpt_sovits_language,
                    )
                    if success and await synthesizer.is_available(cid):
                        logger.info(f"[RenderManager] 캐릭터 자동 준비 완료: {cid}")
                        return True
                return False

            for dialogue in job.dialogues:
                if self._cancel_requested:
                    self._progress.status = RenderStatus.CANCELLED
                    self._progress.finished_at = datetime.now().isoformat()
                    await self._notify_progress()
                    break

                index = dialogue["index"]
                char_id = dialogue.get("char_id")
                speaker_name = dialogue.get("speaker_name")
                text = dialogue["text"]

                # 이미 렌더링된 경우 스킵
                if index in rendered_indices:
                    continue

                self._progress.current_index = index
                self._progress.current_text = text[:30] + "..." if len(text) > 30 else text
                await self._notify_progress()

                # 사용할 캐릭터 ID 결정
                char_id_to_use = char_id

                # 매핑 키 (char_id가 없으면 name: 접두사 사용)
                # 따옴표는 게임 내 역할극 강조 표시이므로 유지 (예: '오니')
                mapping_key = char_id or (f"name:{speaker_name}" if speaker_name else None)

                # 별칭 매핑 확인 (speaker_name으로 음성 있는 캐릭터 찾기)
                alias_char_id = resolve_voice_char_id(speaker_name=speaker_name, char_id=char_id)

                logger.info(f"[RenderManager] 대사 {index}: char_id={char_id}, speaker_name={speaker_name}, alias={alias_char_id}")

                if not char_id_to_use:
                    # char_id가 없는 경우
                    if alias_char_id and await ensure_char_ready(alias_char_id):
                        # 별칭으로 찾은 캐릭터 사용
                        logger.info(f"[RenderManager] 별칭 매핑 사용: {speaker_name} → {alias_char_id}")
                        char_id_to_use = alias_char_id
                    elif mapping_key and mapping_key in job.speaker_voice_map:
                        # 수동 매핑 사용
                        mapped = job.speaker_voice_map[mapping_key]
                        logger.info(f"[RenderManager] 수동 매핑 사용: {mapping_key} → {mapped}")
                        char_id_to_use = mapped
                    else:
                        # 나레이션/기본 음성 사용
                        char_id_to_use = job.narrator_char_id or job.default_char_id
                        logger.info(f"[RenderManager] 나레이션/기본 음성 → {char_id_to_use}")
                elif await ensure_char_ready(char_id_to_use):
                    # 캐릭터 자신의 모델이 있으면 (또는 자동 준비 성공하면) 그대로 사용
                    logger.info(f"[RenderManager] 캐릭터 음성 사용: {char_id_to_use}")
                elif alias_char_id and await ensure_char_ready(alias_char_id):
                    # 별칭으로 찾은 캐릭터 사용
                    logger.info(f"[RenderManager] 별칭 매핑 사용: {speaker_name} → {alias_char_id}")
                    char_id_to_use = alias_char_id
                elif char_id_to_use in job.speaker_voice_map:
                    # 모델 없고 수동 매핑이 있으면 사용
                    mapped = job.speaker_voice_map[char_id_to_use]
                    logger.info(f"[RenderManager] 수동 매핑 사용: {char_id_to_use} → {mapped}")
                    char_id_to_use = mapped
                else:
                    # 모델도 없고 매핑도 없으면 - default_char_id 사용
                    logger.info(f"[RenderManager] 기본 음성 사용: {char_id_to_use} → {job.default_char_id}")
                    char_id_to_use = job.default_char_id

                # 음성 합성
                audio_path = self.cache.get_audio_path(episode_id, index)
                audio_path.parent.mkdir(parents=True, exist_ok=True)

                if char_id_to_use and await synthesizer.is_available(char_id_to_use):
                    # GPU 세마포어: OCR과 동시 실행 방지
                    async with gpu_semaphore_context():
                        # GPT-SoVITS로 합성 (실시간 TTS와 동일한 config 파라미터 사용)
                        gpt_config = synthesizer.config
                        result = await synthesizer.synthesize(
                            char_id_to_use,
                            text,
                            output_path=audio_path,
                            language=app_config.gpt_sovits_language,
                            speed_factor=gpt_config.speed_factor,
                            top_k=gpt_config.top_k,
                            top_p=gpt_config.top_p,
                            temperature=gpt_config.temperature,
                        )
                    duration = result.duration if result else 0.0
                else:
                    # 사용 가능한 모델 없음 - 스킵
                    logger.warning(f"[RenderManager] 사용 가능한 모델 없음: {char_id} (기본: {job.default_char_id})")
                    continue

                # 캐시에 추가
                if audio_path.exists():
                    self.cache.add_audio(
                        episode_id, index, char_id, text, duration, audio_path
                    )
                    self._progress.completed += 1
                    await self._notify_progress()

            # 완료 처리
            if not self._cancel_requested:
                self._progress.status = RenderStatus.COMPLETED
                self._progress.current_index = None
                self._progress.current_text = None
                self._progress.finished_at = datetime.now().isoformat()
                await self._notify_progress()
                logger.info(f"렌더링 완료: {episode_id}")

        except Exception as e:
            logger.error(f"렌더링 실패 ({episode_id}): {e}")
            self._progress.status = RenderStatus.FAILED
            self._progress.error = str(e)
            self._progress.finished_at = datetime.now().isoformat()
            await self._notify_progress()

        finally:
            self._current_job = None


# 싱글톤 인스턴스
_render_manager: RenderManager | None = None


def get_render_manager() -> RenderManager:
    """렌더링 관리자 싱글톤"""
    global _render_manager
    if _render_manager is None:
        _render_manager = RenderManager()
    return _render_manager
