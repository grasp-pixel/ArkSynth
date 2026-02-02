"""스토리 텍스트 파서"""

import re
from pathlib import Path

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
    # 파라미터 파싱 정규식
    PARAM_PATTERN = re.compile(r'(\w+)=(?:"([^"]*)"|([^,\s)]+))')

    # 커맨드 타입 매핑
    COMMAND_TYPE_MAP = {
        "HEADER": CommandType.HEADER,
        "Background": CommandType.BACKGROUND,
        "Character": CommandType.CHARACTER,
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
        self._current_characters: list[str] = []  # 현재 화면의 캐릭터 ID들

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

                # 스피커 ID 추측 (현재 캐릭터 목록에서)
                speaker_id = self._guess_speaker_id(speaker_name)

                if speaker_id:
                    # char_002_amiya_1#6 -> char_002_amiya 형태로 정규화
                    normalized_id = self._normalize_char_id(speaker_id)
                    characters.add(normalized_id)
                elif speaker_name:
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
        """현재 화면의 캐릭터 목록 업데이트"""
        self._current_characters = []

        # name, name2 파라미터에서 캐릭터 ID 추출
        for key in ["name", "name2", "name3"]:
            if key in params and params[key]:
                self._current_characters.append(params[key])

    def _guess_speaker_id(self, speaker_name: str) -> str | None:
        """스피커 이름으로 캐릭터 ID 추측

        현재 화면에 표시된 캐릭터 목록에서 매칭 시도
        """
        if not speaker_name or not self._current_characters:
            return None

        # 첫 번째 캐릭터를 기본값으로 사용 (단순 휴리스틱)
        # 실제로는 캐릭터 이름 매핑 테이블을 사용해야 함
        if self._current_characters:
            return self._current_characters[0]

        return None

    def _normalize_char_id(self, char_id: str) -> str:
        """캐릭터 ID 정규화

        char_002_amiya_1#6 -> char_002_amiya
        char_130_doberm_ex -> char_130_doberm
        char_002_amiya_1 -> char_002_amiya
        """
        # 공백 제거
        char_id = char_id.strip()
        # #숫자 제거
        char_id = re.sub(r"#\d+$", "", char_id)
        # _숫자 제거 (끝에 있는 경우, char_숫자_name_숫자 패턴에서 마지막 숫자)
        char_id = re.sub(r"_\d+$", "", char_id)
        # _ex 제거
        char_id = re.sub(r"_ex$", "", char_id)

        return char_id

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
