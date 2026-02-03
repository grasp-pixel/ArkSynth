"""캐릭터-음성 매핑 관리"""

import json
from pathlib import Path
from dataclasses import dataclass


@dataclass
class VoiceInfo:
    """캐릭터 음성 정보"""

    char_id: str
    voice_folder: Path
    file_count: int
    total_duration_seconds: float | None = None


class CharacterVoiceMapper:
    """캐릭터 ID와 음성 파일 매핑 관리

    extracted/ 폴더의 음성 파일과 게임 데이터의 캐릭터 정보를 연결
    """

    def __init__(
        self,
        extracted_path: str | Path,
        gamedata_path: str | Path | None = None,
    ):
        """
        Args:
            extracted_path: 추출된 음성 파일 루트 경로 (extracted/)
            gamedata_path: ArknightsGameData 경로 (캐릭터 이름 로드용)
        """
        self.extracted_path = Path(extracted_path)
        self.gamedata_path = Path(gamedata_path) if gamedata_path else None

        # 캐시
        self._voice_info_cache: dict[str, VoiceInfo] | None = None
        self._character_names: dict[str, str] | None = None

    def clear_cache(self):
        """캐시 초기화 (데이터 새로고침 시 호출)"""
        self._voice_info_cache = None
        self._character_names = None

    def set_gamedata_path(self, path: str | Path | None):
        """게임 데이터 경로 변경"""
        self.gamedata_path = Path(path) if path else None
        # 캐릭터 이름 캐시만 초기화
        self._character_names = None

    def scan_voice_folders(self, lang: str = "voice") -> dict[str, VoiceInfo]:
        """음성 폴더 스캔하여 캐릭터별 정보 수집

        Args:
            lang: 언어 폴더명 (voice, voice_cn, voice_kr, voice_en)

        Returns:
            dict[str, VoiceInfo]: {char_id: VoiceInfo} 매핑
        """
        if self._voice_info_cache is not None:
            return self._voice_info_cache

        voice_root = self.extracted_path / lang
        if not voice_root.exists():
            return {}

        result = {}
        for char_folder in voice_root.iterdir():
            if not char_folder.is_dir():
                continue

            char_id = char_folder.name

            # 음성 파일 수집
            audio_files = list(char_folder.glob("*.mp3"))
            audio_files.extend(char_folder.glob("*.wav"))
            audio_files.extend(char_folder.glob("*.ogg"))

            if not audio_files:
                continue

            result[char_id] = VoiceInfo(
                char_id=char_id,
                voice_folder=char_folder,
                file_count=len(audio_files),
            )

        self._voice_info_cache = result
        return result

    def get_voice_files(self, char_id: str, lang: str = "voice") -> list[Path]:
        """캐릭터의 음성 파일 목록 반환

        Args:
            char_id: 캐릭터 ID
            lang: 언어 폴더명

        Returns:
            list[Path]: 음성 파일 경로 목록
        """
        voice_folder = self.extracted_path / lang / char_id

        if not voice_folder.exists():
            return []

        files = []
        for ext in ["*.mp3", "*.wav", "*.ogg"]:
            files.extend(voice_folder.glob(ext))

        return sorted(files)

    def has_voice(self, char_id: str, lang: str = "voice") -> bool:
        """캐릭터 음성 존재 여부 확인"""
        voice_folder = self.extracted_path / lang / char_id
        return voice_folder.exists() and any(voice_folder.iterdir())

    def get_available_characters(self, lang: str = "voice") -> list[str]:
        """음성이 있는 캐릭터 목록 반환"""
        voice_info = self.scan_voice_folders(lang)
        return sorted(voice_info.keys())

    def load_character_names(self, game_lang: str = "zh_CN") -> dict[str, str]:
        """게임 데이터에서 캐릭터 이름 로드

        Returns:
            dict[str, str]: {char_id: name} 매핑
        """
        if self._character_names is not None:
            return self._character_names

        if self.gamedata_path is None:
            return {}

        # arkprts 경로와 기존 경로 모두 시도
        # 언어 코드 매핑: ko_KR -> kr, en_US -> en, ja_JP -> jp, zh_CN -> cn
        lang_to_server = {"ko_KR": "kr", "en_US": "en", "ja_JP": "jp", "zh_CN": "cn"}
        server_code = lang_to_server.get(game_lang, game_lang)

        # 후보 경로들 (우선순위 순)
        candidates = [
            # arkprts 경로 (data/gamedata/kr/gamedata/excel/)
            self.gamedata_path.parent / "gamedata" / server_code / "gamedata" / "excel" / "character_table.json",
            # 기존 경로 (data/gamedata_yostar/ko_KR/gamedata/excel/)
            self.gamedata_path / game_lang / "gamedata" / "excel" / "character_table.json",
            # 직접 gamedata 경로 (gamedata_path가 이미 gamedata/kr 인 경우)
            self.gamedata_path / "gamedata" / "excel" / "character_table.json",
        ]

        char_table_path = None
        for candidate in candidates:
            if candidate.exists():
                char_table_path = candidate
                break

        if char_table_path is None:
            return {}

        with open(char_table_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        names = {}
        for char_id, char_data in data.items():
            names[char_id] = char_data.get("name", char_id)

        self._character_names = names
        return names

    def get_character_name(self, char_id: str, game_lang: str = "zh_CN") -> str:
        """캐릭터 ID로 이름 조회"""
        names = self.load_character_names(game_lang)
        return names.get(char_id, char_id)

    def get_voice_summary(self, lang: str = "voice") -> dict:
        """음성 데이터 요약 정보 반환"""
        voice_info = self.scan_voice_folders(lang)

        total_files = sum(v.file_count for v in voice_info.values())

        return {
            "total_characters": len(voice_info),
            "total_files": total_files,
            "characters": {
                char_id: {
                    "file_count": info.file_count,
                    "folder": str(info.voice_folder),
                }
                for char_id, info in voice_info.items()
            },
        }

    def export_mapping(self, output_path: str | Path, lang: str = "voice") -> None:
        """캐릭터-음성 매핑을 JSON으로 내보내기"""
        voice_info = self.scan_voice_folders(lang)
        names = self.load_character_names()

        mapping = {}
        for char_id, info in voice_info.items():
            mapping[char_id] = {
                "name": names.get(char_id, char_id),
                "voice_folder": str(info.voice_folder.relative_to(self.extracted_path)),
                "file_count": info.file_count,
            }

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(mapping, f, ensure_ascii=False, indent=2)
