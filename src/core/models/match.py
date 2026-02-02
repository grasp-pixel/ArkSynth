"""대사 매칭 관련 모델"""

from dataclasses import dataclass
from enum import Enum

from .story import Dialogue


class MatchConfidence(Enum):
    """매칭 신뢰도 등급"""

    HIGH = "high"  # 90% 이상
    MEDIUM = "medium"  # 70-90%
    LOW = "low"  # 50-70%
    NONE = "none"  # 50% 미만


@dataclass
class MatchResult:
    """OCR 텍스트와 스토리 대사의 매칭 결과"""

    dialogue: Dialogue
    similarity: float  # 0.0 ~ 1.0
    episode_index: int  # 에피소드 내 대사 위치

    @property
    def confidence(self) -> MatchConfidence:
        """신뢰도 등급 계산"""
        if self.similarity >= 0.9:
            return MatchConfidence.HIGH
        elif self.similarity >= 0.7:
            return MatchConfidence.MEDIUM
        elif self.similarity >= 0.5:
            return MatchConfidence.LOW
        else:
            return MatchConfidence.NONE

    @property
    def is_reliable(self) -> bool:
        """신뢰할 수 있는 매칭인지"""
        return self.similarity >= 0.7
