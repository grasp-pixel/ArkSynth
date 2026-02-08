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
from ..character.id_normalizer import load_char_table_mapping, resolve_to_table_id

logger = logging.getLogger(__name__)

# 남성 키워드 (프론트엔드 getSpeakerVoice와 동일)
MALE_KEYWORDS = ['남자', '남성', '소년', '청년', '신사', '아저씨']


def simple_hash(s: str) -> int:
    """문자열 해시 함수 (프론트엔드 simpleHash와 동일)"""
    h = 0
    for ch in s:
        h = ((h << 5) - h) + ord(ch)
        # 32bit signed integer 변환 (JavaScript 동작 재현)
        h = h & 0xFFFFFFFF
        if h >= 0x80000000:
            h -= 0x100000000
    return abs(h)


def _resolve_gender_voice(
    speaker_name: str | None,
    mapping_key: str | None,
    default_female_voices: list[str],
    default_male_voices: list[str],
) -> str | None:
    """성별 기반 기본음성 분배 (프론트엔드 getSpeakerVoice step 5와 동일)"""
    if not mapping_key:
        return None
    name_to_check = speaker_name or mapping_key
    is_male = any(kw in name_to_check for kw in MALE_KEYWORDS)
    if is_male and default_male_voices:
        return default_male_voices[simple_hash(mapping_key) % len(default_male_voices)]
    if default_female_voices:
        return default_female_voices[simple_hash(mapping_key) % len(default_female_voices)]
    return None


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
    default_female_voices: list[str] = field(default_factory=list)  # 여성 기본음성 목록
    default_male_voices: list[str] = field(default_factory=list)  # 남성 기본음성 목록
    priority: int = 0


@dataclass
class GroupRenderProgress:
    """그룹 렌더링 진행 상태"""

    group_id: str
    status: RenderStatus
    total_episodes: int
    completed_episodes: int
    current_episode_id: str | None = None
    current_episode_progress: float = 0.0  # 현재 에피소드 진행률 (0~1)
    error: str | None = None
    started_at: str | None = None
    finished_at: str | None = None

    @property
    def overall_progress(self) -> float:
        """전체 진행률 (0~100)"""
        if self.total_episodes == 0:
            return 0.0
        base = (self.completed_episodes / self.total_episodes) * 100
        if self.current_episode_id:
            episode_contrib = (1 / self.total_episodes) * self.current_episode_progress * 100
            return base + episode_contrib
        return base


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

        # 그룹 렌더링 상태
        self._group_progress: GroupRenderProgress | None = None
        self._group_cancel_requested = False
        self._group_task: asyncio.Task | None = None
        self._group_progress_callbacks: list[Callable[[GroupRenderProgress], Any]] = []

    @property
    def is_rendering(self) -> bool:
        return self._task is not None and not self._task.done()

    @property
    def is_group_rendering(self) -> bool:
        return self._group_task is not None and not self._group_task.done()

    @property
    def current_episode_id(self) -> str | None:
        return self._current_job.episode_id if self._current_job else None

    @property
    def current_group_id(self) -> str | None:
        return self._group_progress.group_id if self._group_progress else None

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
        default_female_voices: list[str] | None = None,
        default_male_voices: list[str] | None = None,
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
            default_female_voices=default_female_voices or [],
            default_male_voices=default_male_voices or [],
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

            # character_table ID 매핑 로드 (스프라이트 ID → 실제 ID 변환용)
            load_char_table_mapping(app_config.gamedata_yostar_path)

            # 메타데이터 생성 또는 로드
            meta = self.cache.get_meta(episode_id)
            if meta is None:
                meta = self.cache.create_meta(
                    episode_id, len(job.dialogues), gpt_language
                )

            # 이미 렌더링된 인덱스
            rendered_indices = {a.index for a in meta.audios}
            self._progress.completed = len(rendered_indices)

            # 이름 기반 상속 맵 구축
            # 같은 speaker_name이 char_id 있는 대사와 없는 대사로 모두 등장할 때,
            # char_id 없는 대사도 같은 음성 매핑을 상속받도록 함
            # 예: "바운티 헌터" → char_id="avg_npc_009"(일부) + char_id=None(일부)
            name_to_voice: dict[str, str] = {}
            for d in job.dialogues:
                cid = d.get("char_id")
                sname = d.get("speaker_name")
                if cid and sname and sname not in name_to_voice:
                    resolved_cid = resolve_to_table_id(cid)
                    if resolved_cid in job.speaker_voice_map:
                        name_to_voice[sname] = job.speaker_voice_map[resolved_cid]

            if name_to_voice:
                logger.info(f"[RenderManager] 이름 상속 맵: {name_to_voice}")

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
                audio_dir = config.extracted_path / config.voice_language / cid
                if audio_dir.exists():
                    logger.info(f"[RenderManager] 캐릭터 자동 준비 시도: {cid}")
                    output_dir = config.models_path / "gpt_sovits" / cid
                    from ..backend.config import config as server_config
                    gamedata_path = server_config.gamedata_yostar_path
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
                # 스프라이트 ID → character_table ID 변환
                # 예: char_474_gladiia → char_474_glady
                if char_id:
                    char_id = resolve_to_table_id(char_id)
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

                # 별칭 매핑 확인 (char_id 또는 speaker_name으로 음성 있는 캐릭터 찾기)
                alias_char_id = resolve_voice_char_id(char_id or speaker_name)

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
                    elif speaker_name and speaker_name in name_to_voice:
                        # 이름 상속: 같은 이름의 다른 대사에서 char_id 매핑 사용
                        char_id_to_use = name_to_voice[speaker_name]
                        logger.info(f"[RenderManager] 이름 상속 매핑: {speaker_name} → {char_id_to_use}")
                    else:
                        # 성별 기반 기본음성 분배 시도 (화자 이름이 있는 경우)
                        gender_voice = _resolve_gender_voice(
                            speaker_name, mapping_key,
                            job.default_female_voices, job.default_male_voices,
                        ) if speaker_name else None
                        if gender_voice:
                            char_id_to_use = gender_voice
                            logger.info(f"[RenderManager] 성별 기본음성: {speaker_name} → {char_id_to_use}")
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
                elif speaker_name and speaker_name in name_to_voice:
                    # 이름 상속: 같은 이름의 다른 char_id에서 매핑 사용
                    char_id_to_use = name_to_voice[speaker_name]
                    logger.info(f"[RenderManager] 이름 상속 매핑: {char_id_to_use} ({speaker_name})")
                else:
                    # 성별 기반 기본음성 분배 시도
                    gender_voice = _resolve_gender_voice(
                        speaker_name, mapping_key,
                        job.default_female_voices, job.default_male_voices,
                    )
                    if gender_voice:
                        logger.info(f"[RenderManager] 성별 기본음성: {speaker_name} → {gender_voice}")
                        char_id_to_use = gender_voice
                    else:
                        logger.info(f"[RenderManager] 기본 음성 사용: {char_id_to_use} → {job.default_char_id}")
                        char_id_to_use = job.default_char_id

                # 음성 합성
                audio_path = self.cache.get_audio_path(episode_id, index)
                audio_path.parent.mkdir(parents=True, exist_ok=True)

                # 최종 폴백: 모델 없으면 narrator/default로 재시도
                if not char_id_to_use or not await synthesizer.is_available(char_id_to_use):
                    fallback = job.narrator_char_id or job.default_char_id
                    if fallback and fallback != char_id_to_use and await synthesizer.is_available(fallback):
                        logger.info(f"[RenderManager] 최종 폴백: {char_id_to_use} → {fallback}")
                        char_id_to_use = fallback
                    else:
                        logger.warning(f"[RenderManager] 사용 가능한 모델 없음: {char_id} (기본: {job.default_char_id})")
                        continue

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

                # 캐시에 추가
                if audio_path.exists():
                    self.cache.add_audio(
                        episode_id, index, char_id, text, duration, audio_path,
                        voice_char_id=char_id_to_use if char_id_to_use != char_id else None,
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

    # === 그룹 렌더링 ===

    def get_group_progress(self) -> GroupRenderProgress | None:
        """그룹 렌더링 진행 상태 조회"""
        return self._group_progress

    def add_group_progress_callback(self, callback: Callable[[GroupRenderProgress], Any]):
        """그룹 진행률 콜백 등록"""
        self._group_progress_callbacks.append(callback)

    def remove_group_progress_callback(self, callback: Callable[[GroupRenderProgress], Any]):
        """그룹 진행률 콜백 제거"""
        if callback in self._group_progress_callbacks:
            self._group_progress_callbacks.remove(callback)

    async def _notify_group_progress(self):
        """그룹 진행률 콜백 호출"""
        if self._group_progress:
            for callback in self._group_progress_callbacks:
                try:
                    result = callback(self._group_progress)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as e:
                    logger.error(f"그룹 진행률 콜백 오류: {e}")

    async def start_group_render(
        self,
        group_id: str,
        episode_ids: list[str],
        get_dialogues: Callable[[str], list[dict]],
        language: str = "ko",
        default_char_id: str | None = None,
        narrator_char_id: str | None = None,
        speaker_voice_map: dict[str, str] | None = None,
        default_female_voices: list[str] | None = None,
        default_male_voices: list[str] | None = None,
        force: bool = False,
    ) -> GroupRenderProgress:
        """그룹 전체 렌더링 시작

        Args:
            group_id: 그룹 ID
            episode_ids: 에피소드 ID 목록
            get_dialogues: 에피소드 ID로 대사 목록을 가져오는 함수
            language: 언어 코드
            default_char_id: 모델 없는 캐릭터용 기본 음성
            narrator_char_id: 나레이션용 캐릭터
            speaker_voice_map: 화자별 음성 매핑
            default_female_voices: 여성 기본음성 목록
            default_male_voices: 남성 기본음성 목록
            force: 기존 캐시 무시하고 다시 렌더링

        Returns:
            GroupRenderProgress
        """
        if self.is_group_rendering:
            raise ValueError(f"이미 그룹 렌더링 중: {self.current_group_id}")

        if self.is_rendering:
            raise ValueError(f"에피소드 렌더링 중: {self.current_episode_id}")

        # 진행 상태 초기화
        self._group_progress = GroupRenderProgress(
            group_id=group_id,
            status=RenderStatus.RENDERING,
            total_episodes=len(episode_ids),
            completed_episodes=0,
            started_at=datetime.now().isoformat(),
        )

        self._group_cancel_requested = False

        # 백그라운드 태스크 시작
        self._group_task = asyncio.create_task(
            self._group_render_task(
                episode_ids=episode_ids,
                get_dialogues=get_dialogues,
                language=language,
                default_char_id=default_char_id,
                narrator_char_id=narrator_char_id,
                speaker_voice_map=speaker_voice_map or {},
                default_female_voices=default_female_voices or [],
                default_male_voices=default_male_voices or [],
                force=force,
            )
        )

        await self._notify_group_progress()
        return self._group_progress

    async def cancel_group_render(self) -> bool:
        """그룹 렌더링 취소"""
        if not self.is_group_rendering:
            return False

        self._group_cancel_requested = True
        # 현재 진행 중인 에피소드 렌더링도 취소
        if self.is_rendering:
            await self.cancel_render()

        logger.info(f"그룹 렌더링 취소 요청: {self.current_group_id}")
        return True

    async def _group_render_task(
        self,
        episode_ids: list[str],
        get_dialogues: Callable[[str], list[dict]],
        language: str,
        default_char_id: str | None,
        narrator_char_id: str | None,
        speaker_voice_map: dict[str, str],
        default_female_voices: list[str],
        default_male_voices: list[str],
        force: bool,
    ):
        """그룹 렌더링 백그라운드 태스크"""
        if not self._group_progress:
            return

        try:
            for i, episode_id in enumerate(episode_ids):
                if self._group_cancel_requested:
                    self._group_progress.status = RenderStatus.CANCELLED
                    self._group_progress.finished_at = datetime.now().isoformat()
                    await self._notify_group_progress()
                    break

                self._group_progress.current_episode_id = episode_id
                self._group_progress.current_episode_progress = 0.0
                await self._notify_group_progress()

                # 대사 목록 가져오기
                dialogues = get_dialogues(episode_id)
                if not dialogues:
                    logger.warning(f"대사 없음, 스킵: {episode_id}")
                    self._group_progress.completed_episodes += 1
                    continue

                # 에피소드 렌더링 (에피소드 진행률 콜백 등록)
                def episode_progress_callback(progress: RenderProgress):
                    if self._group_progress:
                        self._group_progress.current_episode_progress = (
                            progress.completed / progress.total if progress.total > 0 else 0
                        )
                        # 동기 콜백 호출 (이미 async context 안이므로)
                        asyncio.create_task(self._notify_group_progress())

                self.add_progress_callback(episode_progress_callback)

                try:
                    await self.start_render(
                        episode_id=episode_id,
                        dialogues=dialogues,
                        language=language,
                        default_char_id=default_char_id,
                        narrator_char_id=narrator_char_id,
                        speaker_voice_map=speaker_voice_map,
                        default_female_voices=default_female_voices,
                        default_male_voices=default_male_voices,
                        force=force,
                    )

                    # 에피소드 렌더링 완료 대기
                    if self._task:
                        await self._task

                finally:
                    self.remove_progress_callback(episode_progress_callback)

                # 취소 확인
                if self._group_cancel_requested:
                    break

                self._group_progress.completed_episodes += 1
                self._group_progress.current_episode_progress = 1.0
                await self._notify_group_progress()

            # 완료 처리
            if not self._group_cancel_requested:
                self._group_progress.status = RenderStatus.COMPLETED
                self._group_progress.current_episode_id = None
                self._group_progress.finished_at = datetime.now().isoformat()
                await self._notify_group_progress()
                logger.info(f"그룹 렌더링 완료: {self._group_progress.group_id}")

        except Exception as e:
            logger.error(f"그룹 렌더링 실패: {e}")
            if self._group_progress:
                self._group_progress.status = RenderStatus.FAILED
                self._group_progress.error = str(e)
                self._group_progress.finished_at = datetime.now().isoformat()
                await self._notify_group_progress()


# 싱글톤 인스턴스
_render_manager: RenderManager | None = None


def get_render_manager() -> RenderManager:
    """렌더링 관리자 싱글톤"""
    global _render_manager
    if _render_manager is None:
        _render_manager = RenderManager()
    return _render_manager
