"""스토리 텍스트 파서"""

import re
from pathlib import Path

from ..character import CharacterIdNormalizer
from ..models.story import CommandType, Dialogue, Episode, StoryCommand


class StoryParser:
    """ArknightsGameData 스토리 텍스트 파일 파서

    스토리 파일 형식:
    - [HEADER(...)] - 헤더 정보
    - [Character(name="char_id", ...)] - 캐릭터 표시
    - [name="캐릭터명"] 대사내용 - 대사
    - [Delay(time=...)] - 딜레이
    - 기타 연출 커맨드들
    """

    # 커맨드 파싱 정규식
    COMMAND_PATTERN = re.compile(r"\[(\w+)(?:\(([^)]*)\))?\]")
    # 대사 파싱 정규식: [name="이름"] 대사 또는 [name="이름"]대사
    DIALOGUE_PATTERN = re.compile(r'\[name="([^"]*)"\]\s*(.*)')
    # 파라미터 파싱 정규식 (key = value 형식의 공백 허용)
    PARAM_PATTERN = re.compile(r'(\w+)\s*=\s*(?:"([^"]*)"|([^,\s)]+))')

    # 커맨드 타입 매핑
    COMMAND_TYPE_MAP = {
        "HEADER": CommandType.HEADER,
        "Background": CommandType.BACKGROUND,
        "Character": CommandType.CHARACTER,
        "charslot": CommandType.CHARACTER,  # 캐릭터 슬롯 (스토리 파일에서 주로 사용)
        "name": CommandType.DIALOGUE,
        "Delay": CommandType.DELAY,
        "Blocker": CommandType.BLOCKER,
        "Image": CommandType.IMAGE,
        "PlayMusic": CommandType.PLAY_MUSIC,
        "PlaySound": CommandType.PLAY_SOUND,
        "StopMusic": CommandType.STOP_MUSIC,
        "HideItem": CommandType.HIDE_ITEM,
        "ShowItem": CommandType.SHOW_ITEM,
        "Decision": CommandType.DECISION,
        "Predicate": CommandType.PREDICATE,
        "Subtitle": CommandType.SUBTITLE,
    }

    def __init__(self):
        self._current_characters: list[str] = []  # 현재 화면의 캐릭터 ID들 (Character 커맨드용)
        self._current_focus: int = 1  # 현재 화자 (1=name, 2=name2)
        # charslot 커맨드용 슬롯별 캐릭터 관리
        self._char_slots: dict[str, str] = {}  # slot -> char_id ("l", "r", "m")
        self._focused_slot: str | None = None  # 현재 포커스된 슬롯

    def parse_file(self, filepath: str | Path) -> Episode:
        """스토리 파일을 파싱하여 Episode 객체 반환

        Args:
            filepath: 스토리 텍스트 파일 경로

        Returns:
            Episode: 파싱된 에피소드 객체
        """
        filepath = Path(filepath)

        # 에피소드 ID 추출 (파일명에서)
        episode_id = filepath.stem  # level_main_01-01_beg

        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()

        commands: list[StoryCommand] = []
        dialogues: list[Dialogue] = []
        characters: set[str] = set()
        title = ""

        self._current_characters = []
        self._current_focus = 1
        self._char_slots = {}
        self._focused_slot = None
        dialogue_index = 0

        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue

            # 대사 라인 확인
            dialogue_match = self.DIALOGUE_PATTERN.match(line)
            if dialogue_match:
                speaker_name = dialogue_match.group(1)
                text = dialogue_match.group(2).strip()

                # 스피커 ID 결정 (focus에 따라 현재 화자 선택)
                raw_speaker_id = self._get_speaking_character()

                # 스프라이트 ID 정규화 (avg_npc_1897_1#1$1 -> avg_npc_1897)
                if raw_speaker_id:
                    speaker_id = self._normalize_char_id(raw_speaker_id)
                    characters.add(speaker_id)
                else:
                    speaker_id = None

                if not speaker_id and speaker_name:
                    # 캐릭터 ID가 없어도 화자 이름이 있으면 캐릭터로 취급
                    # NPC, 일반인 등도 캐릭터로 인식
                    characters.add(speaker_name)

                dialogue = Dialogue(
                    id=f"{episode_id}_{dialogue_index:04d}",
                    speaker_id=speaker_id,
                    speaker_name=speaker_name,
                    text=text,
                    line_number=line_num,
                )
                dialogues.append(dialogue)
                dialogue_index += 1

                # 커맨드로도 저장
                cmd = StoryCommand(
                    type=CommandType.DIALOGUE,
                    params={"name": speaker_name},
                    text=text,
                    line_number=line_num,
                )
                commands.append(cmd)
                continue

            # 일반 커맨드 파싱
            cmd = self._parse_command_line(line, line_num)
            if cmd:
                commands.append(cmd)

                # 헤더에서 타이틀 추출
                if cmd.type == CommandType.HEADER and cmd.text:
                    title = cmd.text

                # Character 커맨드에서 현재 캐릭터 목록 업데이트
                if cmd.type == CommandType.CHARACTER:
                    self._update_current_characters(cmd.params)

                continue

            # 순수 텍스트 줄 = 나레이션 (커맨드로 시작하지 않는 줄)
            # [로 시작하지 않고, 빈 줄이 아닌 경우
            if not line.startswith("[") and line.strip():
                dialogue = Dialogue(
                    id=f"{episode_id}_{dialogue_index:04d}",
                    speaker_id=None,
                    speaker_name="",
                    text=line.strip(),
                    line_number=line_num,
                )
                dialogues.append(dialogue)
                dialogue_index += 1

                # 커맨드로도 저장
                cmd = StoryCommand(
                    type=CommandType.NARRATION,
                    params={},
                    text=line.strip(),
                    line_number=line_num,
                )
                commands.append(cmd)

        return Episode(
            id=episode_id,
            title=title,
            dialogues=dialogues,
            characters=characters,
            commands=commands,
        )

    def _parse_command_line(self, line: str, line_num: int) -> StoryCommand | None:
        """단일 커맨드 라인 파싱"""
        # [CommandName(params)] 또는 [CommandName] 형식
        match = self.COMMAND_PATTERN.match(line)
        if not match:
            return None

        cmd_name = match.group(1)
        params_str = match.group(2) or ""

        # 파라미터 파싱
        params = self._parse_params(params_str)

        # 커맨드 타입 결정
        cmd_type = self.COMMAND_TYPE_MAP.get(cmd_name, CommandType.UNKNOWN)

        # 텍스트 추출 (HEADER의 경우 ] 뒤의 텍스트)
        text = None
        if cmd_type == CommandType.HEADER:
            end_pos = line.find("]")
            if end_pos != -1 and end_pos + 1 < len(line):
                text = line[end_pos + 1 :].strip()

        return StoryCommand(
            type=cmd_type,
            params=params,
            text=text,
            line_number=line_num,
        )

    def _parse_params(self, params_str: str) -> dict[str, str]:
        """파라미터 문자열 파싱"""
        params = {}
        for match in self.PARAM_PATTERN.finditer(params_str):
            key = match.group(1)
            # 따옴표로 감싼 값 또는 일반 값
            value = match.group(2) if match.group(2) is not None else match.group(3)
            params[key] = value
        return params

    def _update_current_characters(self, params: dict[str, str]) -> None:
        """현재 화면의 캐릭터 목록 및 focus 업데이트

        두 가지 형식 지원:
        1. Character: [Character(name="...", name2="...", focus=1)]
        2. charslot: [charslot(slot="l", name="...", focus="l")]
        """
        # charslot 형식 감지 (slot 파라미터가 있으면 charslot)
        if "slot" in params:
            slot = params.get("slot", "").strip()
            char_name = params.get("name", "").strip()
            focus = params.get("focus", "").strip()

            # 파라미터 없이 [charslot]만 있으면 모든 슬롯 클리어
            if not slot and not char_name:
                self._char_slots.clear()
                self._focused_slot = None
                return

            # 슬롯에 캐릭터 할당
            if slot:
                if char_name:
                    self._char_slots[slot] = char_name
                    # focus가 명시되지 않으면 새로 설정된 캐릭터가 화자
                    if not focus:
                        self._focused_slot = slot
                elif slot in self._char_slots:
                    del self._char_slots[slot]

            # focus가 명시적으로 지정된 경우
            if focus:
                if focus != "n":
                    self._focused_slot = focus
                else:
                    self._focused_slot = None

            return

        # Character 형식 (기존 로직)
        self._current_characters = []
        self._current_focus = 1

        for key in ["name", "name2", "name3"]:
            if key in params and params[key]:
                self._current_characters.append(params[key])

        if "focus" in params:
            try:
                self._current_focus = int(params["focus"])
            except ValueError:
                self._current_focus = 1

    def _get_speaking_character(self) -> str | None:
        """focus에 따라 현재 화자 캐릭터(스프라이트) ID 반환

        charslot 형식: focus="l"/"r"/"m" -> 해당 슬롯의 캐릭터
        Character 형식: focus=1/2 -> name/name2
        """
        # charslot 형식 우선 (슬롯 데이터가 있으면)
        if self._char_slots:
            if self._focused_slot and self._focused_slot in self._char_slots:
                return self._char_slots[self._focused_slot]
            # focus가 없으면 None (화자 불명)
            return None

        # Character 형식 (기존 로직)
        if not self._current_characters:
            return None

        index = self._current_focus - 1
        if 0 <= index < len(self._current_characters):
            return self._current_characters[index]

        return self._current_characters[0]

    def _normalize_char_id(self, char_id: str) -> str:
        """캐릭터 ID 정규화 (통합 모듈 사용)

        char_002_amiya_1#6 -> char_002_amiya
        char_130_doberm_ex -> char_130_doberm
        """
        normalizer = CharacterIdNormalizer()
        return normalizer.normalize(char_id)

    def parse_directory(self, directory: str | Path) -> list[Episode]:
        """디렉토리 내 모든 스토리 파일 파싱"""
        directory = Path(directory)
        episodes = []

        for filepath in sorted(directory.glob("*.txt")):
            try:
                episode = self.parse_file(filepath)
                episodes.append(episode)
            except Exception as e:
                print(f"Failed to parse {filepath}: {e}")

        return episodes
