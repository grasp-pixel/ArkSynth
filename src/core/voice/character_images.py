"""캐릭터 이미지 제공

로컬 추출 이미지만 사용:
- extracted/images/chararts/ (캐릭터 초상화, 우선)
- extracted/images/characters/ (AVG 스토리 스탠딩, 폴백)
"""

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# 로컬 추출 이미지 경로
EXTRACTED_IMAGES_PATH = Path("extracted/images/characters")
EXTRACTED_CHARARTS_PATH = Path("extracted/images/chararts")


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


def get_num_name_pattern(char_id: str) -> str | None:
    """캐릭터 ID에서 숫자_이름 패턴 추출 (파일 검색용)

    예시:
    - char_4202_haruka → 4202_haruka
    - avg_002_amiya → 002_amiya
    """
    lower_id = char_id.lower()

    # char_XXX_name 또는 avg_XXX_name에서 XXX_name 추출
    if match := re.match(r'(?:char|avg|avgnew)_(\d+_[a-z]+\d*)', lower_id):
        return match.group(1)

    return None


def get_char_number(char_id: str) -> str | None:
    """캐릭터 ID에서 숫자 부분만 추출

    예시:
    - char_240_wyvern → 240
    - char_4202_haruka → 4202
    """
    if match := re.match(r'(?:char|avg|avgnew)_(\d+)_', char_id.lower()):
        return match.group(1)
    return None


def _search_in_folder(folder: Path, char_id: str, folder_name: str) -> Path | None:
    """폴더 내에서 이미지 검색 (내부 헬퍼)"""
    all_images = list(folder.glob("*.png"))
    if not all_images:
        return None

    lower_char_id = char_id.lower()
    lower_folder_name = folder_name.lower()
    num_name_pattern = get_num_name_pattern(char_id)

    # char_id로 시작하는 파일
    for img_file in all_images:
        lower_name = img_file.stem.lower()
        if lower_name.startswith(lower_char_id):
            if "_1" in lower_name or "$1" in lower_name:
                return img_file

    # 숫자_이름 패턴
    if num_name_pattern:
        for img_file in all_images:
            lower_name = img_file.stem.lower()
            if num_name_pattern in lower_name:
                if "_1" in lower_name or "$1" in lower_name:
                    return img_file

    # 폴더명이 포함된 파일
    for img_file in all_images:
        lower_name = img_file.stem.lower()
        if folder.name.lower() in lower_name:
            if "_1" in lower_name or "$1" in lower_name:
                return img_file

    # 아무 _1 파일
    for img_file in all_images:
        lower_name = img_file.stem.lower()
        if "_1" in lower_name or "$1" in lower_name:
            return img_file

    # 첫 번째 파일
    all_images.sort(key=lambda p: p.stem.lower())
    return all_images[0] if all_images else None


def find_chararts_image(char_id: str, chararts_path: Path = EXTRACTED_CHARARTS_PATH) -> Path | None:
    """chararts 폴더에서 캐릭터 초상화 찾기

    chararts 구조:
    - extracted/images/chararts/{name}/char_XXX_name.png (파츠 분리, 사용 X)
    - extracted/images/chararts/{name}/char_XXX_name_1.png (완성 이미지, 사용 O)
    - extracted/images/chararts/{name}/char_XXX_name_1b.png (저화질, 사용 X)

    Args:
        char_id: 캐릭터 ID (예: char_002_amiya)
        chararts_path: chararts 경로

    Returns:
        이미지 파일 경로 또는 None
    """
    if not chararts_path.exists():
        return None

    # 폴더명 추출 (char_002_amiya → amiya)
    folder_name = get_char_name_from_id(char_id)
    char_folder = chararts_path / folder_name

    if not char_folder.exists():
        return None

    # 폴더 내 PNG 파일들
    all_images = list(char_folder.glob("*.png"))
    if not all_images:
        return None

    lower_char_id = char_id.lower()

    # 완성 이미지 찾기: _1 또는 _2로 끝나는 파일 (b 제외)
    # 우선순위: char_id_1 > char_id_2 > 아무 _1 > 아무 _2
    best_match: Path | None = None
    best_priority = 999

    for img_file in all_images:
        stem = img_file.stem.lower()

        # b로 끝나면 저화질이므로 제외 (예: char_311_mudrok_1b)
        if stem.endswith('b'):
            continue

        # 숫자 없는 파일은 파츠 분리 이미지이므로 제외
        # char_311_mudrok (X) vs char_311_mudrok_1 (O)
        if not re.search(r'_\d+$', stem):
            continue

        # char_id로 시작하는지 확인
        if stem.startswith(lower_char_id):
            # _1로 끝나면 최우선
            if stem.endswith('_1'):
                return img_file
            # _2로 끝나면 두 번째 우선
            if stem.endswith('_2') and best_priority > 1:
                best_match = img_file
                best_priority = 1
        else:
            # char_id가 아니어도 _1, _2 파일이면 후보
            if stem.endswith('_1') and best_priority > 2:
                best_match = img_file
                best_priority = 2
            elif stem.endswith('_2') and best_priority > 3:
                best_match = img_file
                best_priority = 3

    return best_match


def find_local_image(char_id: str, extracted_path: Path = EXTRACTED_IMAGES_PATH) -> Path | None:
    """로컬 추출 이미지 찾기

    검색 우선순위:
    1. char_id 이름 기반 폴더 검색
    2. 폴더가 없으면 숫자 패턴으로 전체 폴더 검색 (char_240_wyvern → "240" 포함 파일)
    3. 폴더 내에서: char_id 매칭 → 숫자_이름 패턴 → 이름 매칭 → 아무 이미지

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

    # 폴더가 없으면 숫자 패턴 또는 유사 폴더명으로 검색
    if not char_folder.exists():
        char_number = get_char_number(char_id)

        # 1. 숫자 패턴으로 char_ 파일 우선 검색 (가장 정확)
        if char_number:
            # 모든 폴더에서 숫자가 포함된 파일 찾기
            # char_ 접두사 우선, _1 우선
            candidates: list[tuple[int, Path]] = []  # (priority, path)

            for folder in extracted_path.iterdir():
                if not folder.is_dir():
                    continue
                for img_file in folder.glob("*.png"):
                    lower_name = img_file.stem.lower()

                    # char_XXX_ 패턴 (우선순위 높음)
                    if lower_name.startswith(f"char_{char_number}_"):
                        priority = 0
                        if "_1" in lower_name or "$1" in lower_name:
                            priority = -1  # _1 더 우선
                        candidates.append((priority, img_file))
                    # avg_XXX_ 패턴 (우선순위 중간)
                    elif lower_name.startswith(f"avg_{char_number}_") or lower_name.startswith(f"avgnew_{char_number}_"):
                        priority = 10
                        if "_1" in lower_name or "$1" in lower_name:
                            priority = 9
                        candidates.append((priority, img_file))
                    # npc는 낮은 우선순위
                    elif f"npc_{char_number}" in lower_name:
                        candidates.append((20, img_file))

            # NPC가 아닌 결과가 있으면 반환
            non_npc = [c for c in candidates if c[0] < 20]
            if non_npc:
                non_npc.sort(key=lambda x: (x[0], x[1].stem.lower()))
                return non_npc[0][1]

        # 2. 유사 폴더명 검색 (jesica → jessica)
        if len(folder_name) >= 3:
            prefix3 = folder_name[:3].lower()
            matching_folders: list[tuple[int, Path]] = []  # (match_length, folder)
            for folder in extracted_path.iterdir():
                if not folder.is_dir():
                    continue
                folder_lower = folder.name.lower()
                # npc 폴더는 제외
                if folder_lower.startswith('npc') or folder_lower.startswith('avg_npc'):
                    continue
                # 3글자 접두사 일치 + 길이 유사 (오탐 방지)
                if folder_lower.startswith(prefix3) and abs(len(folder_lower) - len(folder_name)) <= 2:
                    # 공통 접두사 길이 계산
                    common_len = 0
                    for i, (a, b) in enumerate(zip(folder_lower, folder_name.lower())):
                        if a == b:
                            common_len = i + 1
                        else:
                            break
                    matching_folders.append((common_len, folder))

            # 가장 많이 일치하는 폴더 먼저 시도
            matching_folders.sort(key=lambda x: -x[0])
            for _, folder in matching_folders:
                result = _search_in_folder(folder, char_id, folder_name)
                if result:
                    return result

        # 3. NPC 이미지라도 있으면 반환 (최후의 폴백)
        if char_number and candidates:
            candidates.sort(key=lambda x: (x[0], x[1].stem.lower()))
            return candidates[0][1]

        return None

    # 폴더 내 모든 이미지
    all_images = list(char_folder.glob("*.png"))
    if not all_images:
        return None

    lower_char_id = char_id.lower()
    lower_folder_name = folder_name.lower()
    num_name_pattern = get_num_name_pattern(char_id)  # 예: "4202_haruka"

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

    # 2단계: 숫자_이름 패턴이 포함된 파일 찾기 (예: avg_4202_haruka_1)
    if num_name_pattern:
        pattern_matches = []
        for img_file in all_images:
            lower_name = img_file.stem.lower()
            if num_name_pattern in lower_name:
                # _1$1 우선
                if "_1$1" in lower_name or "_1.png" in img_file.name.lower():
                    return img_file
                pattern_matches.append(img_file)

        if pattern_matches:
            pattern_matches.sort(key=lambda p: p.stem.lower())
            return pattern_matches[0]

    # 3단계: 캐릭터 이름이 포함된 파일 찾기
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

    # 4단계: 폴더 내 아무 이미지 (정렬 후 첫 번째)
    all_images.sort(key=lambda p: p.stem.lower())
    return all_images[0]


class CharacterImageProvider:
    """캐릭터 이미지 제공 (로컬 추출 이미지만 사용)

    검색 순서:
    1. extracted/images/chararts (캐릭터 초상화, 우선)
    2. extracted/images/characters (AVG 스토리 스탠딩, 폴백)
    """

    def __init__(
        self,
        extracted_path: str | Path | None = None,
        chararts_path: str | Path | None = None,
    ):
        """
        Args:
            extracted_path: 추출 이미지 경로 (기본: extracted/images/characters)
            chararts_path: 캐릭터 초상화 경로 (기본: extracted/images/chararts)
        """
        self.extracted_path = Path(extracted_path) if extracted_path else EXTRACTED_IMAGES_PATH
        self.chararts_path = Path(chararts_path) if chararts_path else EXTRACTED_CHARARTS_PATH

    def get_image(self, char_id: str) -> Path | None:
        """캐릭터 이미지 경로 반환 (chararts 우선, characters 폴백)"""
        # 1. chararts에서 먼저 찾기 (초상화)
        result = find_chararts_image(char_id, self.chararts_path)
        if result:
            return result

        # 2. characters에서 폴백 검색 (스토리 스탠딩)
        return find_local_image(char_id, self.extracted_path)

    def has_image(self, char_id: str) -> bool:
        """이미지가 있는지 확인"""
        return self.get_image(char_id) is not None

    def get_image_count(self) -> int:
        """총 이미지 수 (characters + chararts)"""
        count = 0
        if self.extracted_path.exists():
            count += sum(1 for _ in self.extracted_path.glob("**/*.png"))
        if self.chararts_path.exists():
            count += sum(1 for _ in self.chararts_path.glob("**/*.png"))
        return count

    def get_folder_count(self) -> int:
        """캐릭터 폴더 수 (characters + chararts)"""
        count = 0
        if self.extracted_path.exists():
            count += sum(1 for d in self.extracted_path.iterdir() if d.is_dir())
        if self.chararts_path.exists():
            count += sum(1 for d in self.chararts_path.iterdir() if d.is_dir())
        return count

    def get_char_ids(self) -> set[str]:
        """이미지가 있는 char_id 목록 (characters + chararts)

        폴더 내 파일명에서 char_id 추출
        """
        char_ids = set()

        for base_path in [self.extracted_path, self.chararts_path]:
            if not base_path.exists():
                continue
            for char_folder in base_path.iterdir():
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
