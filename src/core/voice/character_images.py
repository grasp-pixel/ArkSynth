"""캐릭터 이미지 제공

로컬 추출 이미지만 사용 (extracted/images/characters/)
"""

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# 로컬 추출 이미지 경로
EXTRACTED_IMAGES_PATH = Path("extracted/images/characters")


def get_char_name_from_id(char_id: str) -> str:
    """캐릭터 ID에서 이름 추출 (폴더명용)

    예시:
    - char_002_amiya → amiya
    - avg_npc_023 → npc_023
    - char_npc_012 → npc_012
    """
    lower_id = char_id.lower()

    # char_npc_xxx → npc_xxx
    if lower_id.startswith("char_npc_"):
        return lower_id[5:]  # "char_" 제거

    # avg_npc_xxx → npc_xxx
    if lower_id.startswith("avg_npc_"):
        return lower_id[4:]  # "avg_" 제거

    # char_xxx_name → name
    if match := re.match(r'char_\d+_([a-z]+\d*)', lower_id):
        return match.group(1)

    # avg_xxx_name → name
    if match := re.match(r'(?:avg|avgnew)_\d+_([a-z]+\d*)', lower_id):
        return match.group(1)

    return lower_id


def find_local_image(char_id: str, extracted_path: Path = EXTRACTED_IMAGES_PATH) -> Path | None:
    """로컬 추출 이미지 찾기

    검색 우선순위:
    1. char_id로 시작하는 파일 (_1 우선)
    2. 캐릭터 이름이 포함된 파일 (_1 우선)
    3. 폴더 내 아무 이미지

    Args:
        char_id: 캐릭터 ID (예: char_002_amiya, avg_npc_023)
        extracted_path: 추출 이미지 기본 경로

    Returns:
        이미지 파일 경로 또는 None
    """
    if not extracted_path.exists():
        return None

    # 폴더명 추출
    folder_name = get_char_name_from_id(char_id)
    char_folder = extracted_path / folder_name

    if not char_folder.exists():
        return None

    # 폴더 내 모든 이미지
    all_images = list(char_folder.glob("*.png"))
    if not all_images:
        return None

    lower_char_id = char_id.lower()
    lower_folder_name = folder_name.lower()

    # 1단계: char_id로 시작하는 파일 찾기 (대소문자 무시)
    exact_matches = []
    for img_file in all_images:
        lower_name = img_file.stem.lower()
        if lower_name.startswith(lower_char_id):
            suffix = lower_name[len(lower_char_id):]
            if suffix in ("_1", "$1"):
                return img_file  # _1 우선 반환
            exact_matches.append(img_file)

    if exact_matches:
        exact_matches.sort(key=lambda p: p.stem.lower())
        return exact_matches[0]

    # 2단계: 캐릭터 이름이 포함된 파일 찾기
    name_matches = []
    for img_file in all_images:
        lower_name = img_file.stem.lower()
        if lower_folder_name in lower_name:
            # _1 우선
            if "_1" in lower_name or "$1" in lower_name:
                return img_file
            name_matches.append(img_file)

    if name_matches:
        name_matches.sort(key=lambda p: p.stem.lower())
        return name_matches[0]

    # 3단계: 폴더 내 아무 이미지 (정렬 후 첫 번째)
    all_images.sort(key=lambda p: p.stem.lower())
    return all_images[0]


class CharacterImageProvider:
    """캐릭터 이미지 제공 (로컬 추출 이미지만 사용)"""

    def __init__(
        self,
        extracted_path: str | Path | None = None,
    ):
        """
        Args:
            extracted_path: 추출 이미지 경로 (기본: extracted/images/characters)
        """
        self.extracted_path = Path(extracted_path) if extracted_path else EXTRACTED_IMAGES_PATH

    def get_image(self, char_id: str) -> Path | None:
        """캐릭터 이미지 경로 반환"""
        return find_local_image(char_id, self.extracted_path)

    def has_image(self, char_id: str) -> bool:
        """이미지가 있는지 확인"""
        return self.get_image(char_id) is not None

    def get_image_count(self) -> int:
        """총 이미지 수"""
        if not self.extracted_path.exists():
            return 0
        return sum(1 for _ in self.extracted_path.glob("**/*.png"))

    def get_folder_count(self) -> int:
        """캐릭터 폴더 수"""
        if not self.extracted_path.exists():
            return 0
        return sum(1 for d in self.extracted_path.iterdir() if d.is_dir())

    def get_char_ids(self) -> set[str]:
        """이미지가 있는 char_id 목록

        폴더 내 파일명에서 char_id 추출
        """
        if not self.extracted_path.exists():
            return set()

        char_ids = set()
        for char_folder in self.extracted_path.iterdir():
            if not char_folder.is_dir():
                continue
            for img_file in char_folder.glob("*.png"):
                # 파일명에서 _1, $1, #N 등 제거하여 char_id 추출
                stem = img_file.stem
                # char_002_amiya_1 → char_002_amiya
                # char_108_silent_1#1 → char_108_silent_1
                char_id = re.sub(r'[_$#]\d+$', '', stem)
                char_ids.add(char_id)
        return char_ids
