"""렌더링된 음성 캐시 관리"""

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class CachedAudio:
    """캐시된 오디오 정보"""

    index: int  # 대사 인덱스
    char_id: str | None
    text: str
    duration: float  # 초 단위
    file_path: str
    synthesized_at: str
    voice_char_id: str | None = None  # 실제 합성에 사용된 캐릭터 (char_id와 다를 때만)

    @classmethod
    def from_dict(cls, data: dict) -> "CachedAudio":
        # 이전 meta.json 호환: 새 필드 없으면 기본값 사용
        import dataclasses
        field_names = {f.name for f in dataclasses.fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in field_names})

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class EpisodeMeta:
    """에피소드 렌더링 메타데이터"""

    episode_id: str
    total_dialogues: int
    rendered_count: int
    rendered_at: str
    language: str
    audios: list[CachedAudio]

    @classmethod
    def from_dict(cls, data: dict) -> "EpisodeMeta":
        audios = [CachedAudio.from_dict(a) for a in data.get("audios", [])]
        return cls(
            episode_id=data["episode_id"],
            total_dialogues=data["total_dialogues"],
            rendered_count=data["rendered_count"],
            rendered_at=data["rendered_at"],
            language=data["language"],
            audios=audios,
        )

    def to_dict(self) -> dict:
        return {
            "episode_id": self.episode_id,
            "total_dialogues": self.total_dialogues,
            "rendered_count": self.rendered_count,
            "rendered_at": self.rendered_at,
            "language": self.language,
            "audios": [a.to_dict() for a in self.audios],
        }


class RenderCache:
    """에피소드별 렌더링 캐시 관리자

    구조:
        rendered/
        └── {episode_id}/
            ├── meta.json
            ├── 0000.wav
            ├── 0001.wav
            └── ...
    """

    def __init__(self, cache_path: Path | None = None):
        self.cache_path = cache_path or Path("rendered")
        self.cache_path.mkdir(parents=True, exist_ok=True)

    def get_episode_path(self, episode_id: str) -> Path:
        """에피소드 캐시 디렉토리"""
        # episode_id의 슬래시를 언더스코어로 변환
        safe_id = episode_id.replace("/", "_").replace("\\", "_")
        return self.cache_path / safe_id

    def get_meta_path(self, episode_id: str) -> Path:
        """메타 파일 경로"""
        return self.get_episode_path(episode_id) / "meta.json"

    def get_audio_path(self, episode_id: str, index: int) -> Path:
        """오디오 파일 경로"""
        return self.get_episode_path(episode_id) / f"{index:04d}.wav"

    def has_cache(self, episode_id: str) -> bool:
        """에피소드 캐시 존재 여부"""
        return self.get_meta_path(episode_id).exists()

    def is_complete(self, episode_id: str) -> bool:
        """렌더링 완료 여부"""
        meta = self.get_meta(episode_id)
        if meta is None:
            return False
        return meta.rendered_count >= meta.total_dialogues

    def get_meta(self, episode_id: str) -> EpisodeMeta | None:
        """메타데이터 조회"""
        meta_path = self.get_meta_path(episode_id)
        if not meta_path.exists():
            return None

        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return EpisodeMeta.from_dict(data)
        except Exception as e:
            logger.error(f"메타 로드 실패 ({episode_id}): {e}")
            return None

    def save_meta(self, meta: EpisodeMeta):
        """메타데이터 저장"""
        episode_path = self.get_episode_path(meta.episode_id)
        episode_path.mkdir(parents=True, exist_ok=True)

        meta_path = self.get_meta_path(meta.episode_id)
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta.to_dict(), f, ensure_ascii=False, indent=2)

    def create_meta(
        self, episode_id: str, total_dialogues: int, language: str = "ko"
    ) -> EpisodeMeta:
        """새 메타데이터 생성"""
        meta = EpisodeMeta(
            episode_id=episode_id,
            total_dialogues=total_dialogues,
            rendered_count=0,
            rendered_at=datetime.now().isoformat(),
            language=language,
            audios=[],
        )
        self.save_meta(meta)
        return meta

    def add_audio(
        self,
        episode_id: str,
        index: int,
        char_id: str | None,
        text: str,
        duration: float,
        audio_path: Path,
        voice_char_id: str | None = None,
    ) -> CachedAudio:
        """렌더링된 오디오 추가"""
        meta = self.get_meta(episode_id)
        if meta is None:
            raise ValueError(f"메타데이터 없음: {episode_id}")

        # 캐시된 오디오 정보
        cached = CachedAudio(
            index=index,
            char_id=char_id,
            text=text,
            duration=duration,
            file_path=str(audio_path.relative_to(self.get_episode_path(episode_id))),
            synthesized_at=datetime.now().isoformat(),
            voice_char_id=voice_char_id,
        )

        # 메타 업데이트
        meta.audios.append(cached)
        meta.rendered_count = len(meta.audios)
        meta.rendered_at = datetime.now().isoformat()
        self.save_meta(meta)

        return cached

    def get_audio(self, episode_id: str, index: int) -> Path | None:
        """캐시된 오디오 파일 경로"""
        audio_path = self.get_audio_path(episode_id, index)
        if audio_path.exists():
            return audio_path
        return None

    def get_progress(self, episode_id: str) -> tuple[int, int]:
        """렌더링 진행률 (완료, 전체)"""
        meta = self.get_meta(episode_id)
        if meta is None:
            return 0, 0
        return meta.rendered_count, meta.total_dialogues

    def delete_audio(self, episode_id: str, index: int) -> bool:
        """개별 오디오 파일 삭제

        Args:
            episode_id: 에피소드 ID
            index: 대사 인덱스

        Returns:
            삭제 성공 여부
        """
        meta = self.get_meta(episode_id)
        if meta is None:
            return False

        audio_path = self.get_audio_path(episode_id, index)
        if audio_path.exists():
            try:
                audio_path.unlink()
            except Exception as e:
                logger.error(f"오디오 삭제 실패 ({episode_id}/{index}): {e}")
                return False

        # 메타에서 해당 인덱스 항목 제거
        meta.audios = [a for a in meta.audios if a.index != index]
        meta.rendered_count = len(meta.audios)
        meta.rendered_at = datetime.now().isoformat()
        self.save_meta(meta)

        logger.info(f"오디오 삭제: {episode_id}/{index} (남은 {meta.rendered_count}개)")
        return True

    def delete_cache(self, episode_id: str) -> bool:
        """에피소드 캐시 삭제"""
        episode_path = self.get_episode_path(episode_id)
        if not episode_path.exists():
            return False

        try:
            import shutil

            shutil.rmtree(episode_path)
            logger.info(f"캐시 삭제: {episode_id}")
            return True
        except Exception as e:
            logger.error(f"캐시 삭제 실패 ({episode_id}): {e}")
            return False

    def list_cached_episodes(self, complete_only: bool = True) -> list[str]:
        """캐시된 에피소드 목록

        Args:
            complete_only: True면 완료된 에피소드만, False면 부분 완료 포함
        """
        if not self.cache_path.exists():
            return []

        episodes = []
        for episode_dir in self.cache_path.iterdir():
            if episode_dir.is_dir():
                meta_path = episode_dir / "meta.json"
                if meta_path.exists():
                    if complete_only:
                        # 완료 여부 확인
                        try:
                            with open(meta_path, "r", encoding="utf-8") as f:
                                data = json.load(f)
                            if data.get("rendered_count", 0) >= data.get("total_dialogues", 0):
                                episodes.append(episode_dir.name)
                        except Exception:
                            pass  # 오류 시 스킵
                    else:
                        episodes.append(episode_dir.name)

        return sorted(episodes)

    def list_partial_episodes(self) -> list[str]:
        """부분 완료된 에피소드 목록 (캐시 있지만 완료되지 않은 것)"""
        if not self.cache_path.exists():
            return []

        episodes = []
        for episode_dir in self.cache_path.iterdir():
            if episode_dir.is_dir():
                meta_path = episode_dir / "meta.json"
                if meta_path.exists():
                    try:
                        with open(meta_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        rendered = data.get("rendered_count", 0)
                        total = data.get("total_dialogues", 0)
                        if rendered > 0 and rendered < total:
                            episodes.append(episode_dir.name)
                    except Exception:
                        pass  # 오류 시 스킵

        return sorted(episodes)

    def get_cache_size(self, episode_id: str) -> int:
        """에피소드 캐시 크기 (바이트)"""
        episode_path = self.get_episode_path(episode_id)
        if not episode_path.exists():
            return 0

        total = 0
        for file in episode_path.rglob("*"):
            if file.is_file():
                total += file.stat().st_size

        return total


# 싱글톤 인스턴스
_render_cache: RenderCache | None = None


def get_render_cache() -> RenderCache:
    """캐시 싱글톤 인스턴스"""
    global _render_cache
    if _render_cache is None:
        _render_cache = RenderCache()
    return _render_cache
