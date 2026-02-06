"""handbook_info_table.json에서 캐릭터 본명 자동 추출

사용법:
    python -m src.tools.extract_realnames --dry-run  # 추출 결과 미리보기
    python -m src.tools.extract_realnames             # character_aliases.json에 저장
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

# 프로젝트 루트 경로
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_PATH = PROJECT_ROOT / "data"
GAMEDATA_PATH = DATA_PATH / "gamedata" / "kr" / "gamedata" / "excel"
ALIASES_PATH = DATA_PATH / "character_aliases.json"

# 본명 추출 정규식 패턴들
REALNAME_PATTERNS = [
    # "본명은 XXX," 또는 "본명은 XXX." 패턴 (가장 정확)
    r"본명은\s+([가-힣a-zA-Z·\-\s]{2,30}?)[,\.。]",
    # "본명은 XXX라고" 패턴
    r"본명은\s+([가-힣a-zA-Z·\-\s]{2,30}?)라고",
    # "본명은 XXX이다/였다" 패턴
    r"본명은\s+([가-힣a-zA-Z·\-\s]{2,30}?)(?:이다|였다)",
]


def load_handbook_info() -> dict:
    """handbook_info_table.json 로드"""
    handbook_path = GAMEDATA_PATH / "handbook_info_table.json"
    if not handbook_path.exists():
        print(f"오류: handbook_info_table.json을 찾을 수 없습니다: {handbook_path}")
        sys.exit(1)

    with open(handbook_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_character_table() -> dict:
    """character_table.json 로드 (캐릭터 이름 조회용)"""
    char_table_path = GAMEDATA_PATH / "character_table.json"
    if not char_table_path.exists():
        print(f"오류: character_table.json을 찾을 수 없습니다: {char_table_path}")
        sys.exit(1)

    with open(char_table_path, "r", encoding="utf-8") as f:
        return json.load(f)


def clean_realname(realname: str) -> str:
    """추출된 본명에서 한국어 조사 제거"""
    # 끝에 붙은 조사 패턴들
    suffixes_to_remove = [
        "이다", "였다", "이며", "로서", "로써",
        "라고", "라는", "란", "다", "로",
    ]

    cleaned = realname.strip()
    for suffix in suffixes_to_remove:
        if cleaned.endswith(suffix) and len(cleaned) > len(suffix) + 2:
            cleaned = cleaned[:-len(suffix)].strip()
            break

    return cleaned


def extract_realname_from_text(text: str) -> str | None:
    """텍스트에서 본명 추출"""
    for pattern in REALNAME_PATTERNS:
        match = re.search(pattern, text)
        if match:
            realname = match.group(1).strip()
            # 조사 제거
            realname = clean_realname(realname)
            # 너무 짧거나 긴 이름 필터링
            if 2 <= len(realname) <= 20:
                return realname
    return None


def extract_all_realnames(handbook: dict, char_table: dict) -> dict[str, dict]:
    """모든 캐릭터의 본명 추출

    Returns:
        {char_id: {"realname": "조르디 폰타나로사", "codename": "루멘"}}
    """
    results = {}
    handbook_dict = handbook.get("handbookDict", {})

    for char_id, char_data in handbook_dict.items():
        # 플레이어블 캐릭터만 (char_로 시작, npc 제외)
        if not char_id.startswith("char_") or "_npc_" in char_id:
            continue

        # storyTextAudio에서 본명 검색
        for audio in char_data.get("storyTextAudio", []):
            for story in audio.get("stories", []):
                text = story.get("storyText", "")
                if "본명" in text:
                    realname = extract_realname_from_text(text)
                    if realname:
                        # 캐릭터 코드네임 조회
                        codename = char_table.get(char_id, {}).get("name", "")
                        results[char_id] = {
                            "realname": realname,
                            "codename": codename,
                        }
                        break
            if char_id in results:
                break

    return results


def split_name_parts(realname: str) -> list[str]:
    """본명을 부분으로 분리 (전체, 이름, 성 등)

    Returns:
        ["아지무 안젤리나", "안젤리나", "아지무"] 또는 ["조르디"] (단일 이름)
    """
    parts = [realname]  # 전체 이름은 항상 포함

    # 공백으로 분리된 경우
    words = realname.split()
    if len(words) >= 2:
        parts.extend(words)

    # 중간점(·)으로 분리된 경우 (예: "하이디·톰슨")
    if "·" in realname:
        parts.extend(realname.split("·"))

    # 중복 제거 및 필터링 (2글자 이상)
    unique_parts = []
    seen = set()
    for part in parts:
        part = part.strip()
        if part and len(part) >= 2 and part not in seen:
            unique_parts.append(part)
            seen.add(part)

    return unique_parts


def build_aliases_with_conflict_check(
    realnames: dict[str, dict],
) -> tuple[dict[str, str], dict[str, list[str]]]:
    """충돌 체크하여 별칭 딕셔너리 생성

    Returns:
        (aliases, conflicts)
        aliases: {별칭: char_id}
        conflicts: {별칭: [char_id1, char_id2, ...]}
    """
    # 1단계: 모든 부분 이름이 어떤 캐릭터들에서 나오는지 수집
    part_to_chars: dict[str, list[str]] = defaultdict(list)

    for char_id, data in realnames.items():
        realname = data["realname"]
        parts = split_name_parts(realname)
        for part in parts:
            part_to_chars[part].append(char_id)

    # 2단계: 고유한 부분만 별칭으로 등록, 충돌은 기록
    aliases = {}
    conflicts = {}

    for part, char_ids in part_to_chars.items():
        if len(char_ids) == 1:
            # 고유함 → 별칭 등록
            aliases[part] = char_ids[0]
        else:
            # 충돌 → 등록 안 함, 충돌 기록
            conflicts[part] = char_ids

    return aliases, conflicts


def load_existing_aliases() -> dict:
    """기존 character_aliases.json 로드"""
    if not ALIASES_PATH.exists():
        return {"_version": 1, "aliases": {}}

    with open(ALIASES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_aliases(aliases: dict[str, str], conflicts: dict[str, list[str]]) -> None:
    """character_aliases.json에 저장"""
    existing = load_existing_aliases()

    # 기존 별칭과 병합 (기존 것 유지, 새로운 것 추가)
    merged_aliases = existing.get("aliases", {})
    new_count = 0
    for alias, char_id in aliases.items():
        if alias not in merged_aliases:
            merged_aliases[alias] = char_id
            new_count += 1

    data = {
        "_version": 1,
        "_comment": "캐릭터 별칭 매핑 (화자 이름 → char_id). extract_realnames.py로 자동 생성/갱신 가능",
        "aliases": merged_aliases,
    }

    # 충돌 정보도 저장 (참고용)
    if conflicts:
        data["_conflicts"] = conflicts

    with open(ALIASES_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n저장 완료: {ALIASES_PATH}")
    print(f"  - 새로 추가된 별칭: {new_count}개")
    print(f"  - 전체 별칭: {len(merged_aliases)}개")


def main():
    parser = argparse.ArgumentParser(
        description="handbook에서 캐릭터 본명을 추출하여 별칭으로 등록"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="실제 저장 없이 추출 결과만 출력",
    )
    args = parser.parse_args()

    print("캐릭터 본명 추출 시작...\n")

    # 데이터 로드
    handbook = load_handbook_info()
    char_table = load_character_table()

    # 본명 추출
    realnames = extract_all_realnames(handbook, char_table)
    print(f"본명이 발견된 캐릭터: {len(realnames)}명\n")

    if not realnames:
        print("본명을 찾을 수 없습니다.")
        return

    # 별칭 생성 (충돌 체크)
    aliases, conflicts = build_aliases_with_conflict_check(realnames)

    # 결과 출력
    print("=" * 60)
    print("추출된 본명 목록")
    print("=" * 60)
    for char_id, data in sorted(realnames.items(), key=lambda x: x[1]["codename"]):
        parts = split_name_parts(data["realname"])
        print(f"\n{data['codename']} ({char_id})")
        print(f"  본명: {data['realname']}")
        print(f"  등록될 별칭: {', '.join(p for p in parts if p in aliases)}")
        skipped = [p for p in parts if p in conflicts]
        if skipped:
            print(f"  충돌로 스킵: {', '.join(skipped)}")

    # 충돌 목록
    if conflicts:
        print("\n" + "=" * 60)
        print("충돌로 스킵된 별칭 (수동 검토 필요)")
        print("=" * 60)
        for part, char_ids in sorted(conflicts.items()):
            codenames = [char_table.get(cid, {}).get("name", cid) for cid in char_ids]
            print(f"  '{part}' → {', '.join(codenames)}")

    # 저장
    if not args.dry_run:
        print("\n")
        save_aliases(aliases, conflicts)
    else:
        print(f"\n[DRY-RUN] 저장되지 않음. 실제 저장하려면 --dry-run 옵션 제거")
        print(f"  - 등록 예정 별칭: {len(aliases)}개")


if __name__ == "__main__":
    main()
