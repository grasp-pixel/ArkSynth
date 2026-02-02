"""스토리 데이터 모델"""

from dataclasses import dataclass, field
from enum import Enum


class StoryCategory(Enum):
    """스토리 카테고리"""

    MAINLINE = "mainline"  # 메인 스토리
    EVENT = "event"  # 이벤트 스토리
    SIDE = "side"  # 사이드 스토리
    MINI = "mini"  # 미니 스토리
    OTHER = "other"  # 기타 (튜토리얼, 메모리 등)


class CommandType(Enum):
    """스토리 커맨드 타입"""

    HEADER = "HEADER"
    BACKGROUND = "Background"
    CHARACTER = "Character"
    DIALOGUE = "name"
    DELAY = "Delay"
    BLOCKER = "Blocker"
    IMAGE = "Image"
    PLAY_MUSIC = "PlayMusic"
    PLAY_SOUND = "PlaySound"
    STOP_MUSIC = "StopMusic"
    HIDE_ITEM = "HideItem"
    SHOW_ITEM = "ShowItem"
    DECISION = "Decision"
    PREDICATE = "Predicate"
    SUBTITLE = "Subtitle"
    UNKNOWN = "Unknown"


@dataclass
class StoryCommand:
    """스토리 파일의 개별 커맨드"""

    type: CommandType
    params: dict[str, str] = field(default_factory=dict)
    text: str | None = None
    line_number: int = 0


@dataclass
class StoryGroup:
    """스토리 그룹 (챕터/이벤트 단위)"""

    id: str  # "main_0", "act12side" 등
    name: str  # "암흑 시대·상", "도솔레스 홀리데이"
    category: StoryCategory
    entry_type: str  # 원본 entryType (MAINLINE, ACTIVITY 등)
    act_type: str = ""  # 원본 actType (ACTIVITY_STORY 등)
    episode_count: int = 0
    sort_key: int = 0  # 정렬용


@dataclass
class Character:
    """캐릭터 정보"""

    char_id: str  # char_002_amiya
    name_ko: str  # 아미야
    name_cn: str | None = None
    name_en: str | None = None
    name_jp: str | None = None

    def get_name(self, lang: str = "ko") -> str:
        """언어별 이름 반환"""
        names = {
            "ko": self.name_ko,
            "cn": self.name_cn,
            "en": self.name_en,
            "jp": self.name_jp,
        }
        return names.get(lang) or self.name_ko


@dataclass
class Dialogue:
    """개별 대사"""

    id: str  # 에피소드 내 고유 ID
    speaker_id: str | None  # 캐릭터 ID (None이면 나레이션)
    speaker_name: str  # 표시되는 이름
    text: str  # 대사 내용
    line_number: int  # 원본 파일 라인 번호

    @property
    def is_narration(self) -> bool:
        """나레이션 여부"""
        return self.speaker_id is None or self.speaker_name == ""


@dataclass
class Episode:
    """에피소드 (스토리 단위)"""

    id: str  # 에피소드 ID (예: main_01-01)
    title: str  # 에피소드 제목
    dialogues: list[Dialogue] = field(default_factory=list)
    characters: set[str] = field(default_factory=set)  # 등장 캐릭터 ID 집합
    commands: list[StoryCommand] = field(default_factory=list)

    @property
    def dialogue_count(self) -> int:
        return len(self.dialogues)

    @property
    def character_count(self) -> int:
        return len(self.characters)

    def get_dialogue_by_index(self, index: int) -> Dialogue | None:
        """인덱스로 대사 조회"""
        if 0 <= index < len(self.dialogues):
            return self.dialogues[index]
        return None

    def get_dialogues_by_speaker(self, speaker_id: str) -> list[Dialogue]:
        """특정 캐릭터의 대사만 필터링"""
        return [d for d in self.dialogues if d.speaker_id == speaker_id]
