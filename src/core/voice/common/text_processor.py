"""TTS용 텍스트 전처리 공통 모듈

여러 TTS 엔진에서 사용하는 텍스트 전처리 및 분할 로직.
"""

import re

# ============ 숫자→한국어 변환 상수 ============

# 한자어 수사
_SINO_DIGITS = {1: "일", 2: "이", 3: "삼", 4: "사", 5: "오",
                6: "육", 7: "칠", 8: "팔", 9: "구"}

# 고유어 수사 관형사형 (카운터 앞)
_NATIVE_ONES = {1: "한", 2: "두", 3: "세", 4: "네", 5: "다섯",
                6: "여섯", 7: "일곱", 8: "여덟", 9: "아홉"}

_NATIVE_TENS = {10: "열", 20: "스무", 30: "서른", 40: "마흔", 50: "쉰",
                60: "예순", 70: "일흔", 80: "여든", 90: "아흔"}

# 20+α 합성형: 스물한, 스물두 (스무X → 스물X)
_NATIVE_TENS_COMPOUND = {**_NATIVE_TENS, 20: "스물"}

# 한자어 접미사
_SINO_SUFFIXES = frozenset({
    "년", "월", "일", "원", "분", "초", "번", "호", "층", "도",
    "퍼센트", "프로", "세기", "주년", "주일", "주", "배",
    "미터", "킬로", "그램", "리터", "톤",
    "세", "인분", "인", "차", "위", "시간",
})

# 고유어 접미사
_NATIVE_SUFFIXES = frozenset({
    "명", "개", "살", "마리", "대", "벌", "채",
    "자루", "그루", "송이", "잔", "병", "판", "통",
    "권", "장", "쪽", "줄", "곳", "가지", "번째",
    "시",  # 3시 = 세 시 (시간은 한자어)
})

# 접미사 regex (긴 것부터 매칭)
_ALL_SUFFIXES_SORTED = sorted(_SINO_SUFFIXES | _NATIVE_SUFFIXES, key=len, reverse=True)
_SUFFIX_RE = "|".join(re.escape(s) for s in _ALL_SUFFIXES_SORTED)


# ============ 숫자→한국어 변환 함수 ============

def _four_digits_to_sino(n: int) -> str:
    """4자리 이하 숫자를 한자어로 변환 (일십→십, 일백→백, 일천→천)"""
    parts = []
    for val, unit in [(n // 1000, "천"), (n % 1000 // 100, "백"),
                      (n % 100 // 10, "십"), (n % 10, "")]:
        if val == 0:
            continue
        if val == 1 and unit:
            parts.append(unit)
        else:
            parts.append(_SINO_DIGITS[val] + unit)
    return "".join(parts)


def _number_to_sino(n: int) -> str:
    """정수를 한자어 수사로 변환 (예: 20→이십, 1234→천이백삼십사)"""
    if n == 0:
        return "영"

    large_units = ["", "만", "억", "조", "경"]
    s = str(n)
    groups = []
    while s:
        groups.append(int(s[-4:]))
        s = s[:-4]

    parts = []
    for i, group_val in enumerate(groups):
        if group_val == 0:
            continue
        unit = large_units[i] if i < len(large_units) else ""
        # 일만→만, 일억→억, 일조→조 (상위 그룹에서 1은 생략)
        if group_val == 1 and unit:
            parts.append(unit)
        else:
            parts.append(_four_digits_to_sino(group_val) + unit)

    return "".join(reversed(parts))


def _number_to_native(n: int) -> str | None:
    """정수를 고유어 수사 관형사형으로 변환 (1-99만 지원)

    Returns None if n > 99 or n < 1.
    """
    if n < 1 or n > 99:
        return None

    tens = (n // 10) * 10
    ones = n % 10

    if tens and ones:
        return _NATIVE_TENS_COMPOUND[tens] + _NATIVE_ONES[ones]
    elif tens:
        return _NATIVE_TENS[tens]
    else:
        return _NATIVE_ONES[ones]


def _replace_number_suffix(m: re.Match) -> str:
    """숫자+접미사 패턴 치환 콜백"""
    num = int(m.group(1))
    large_unit = m.group(2) or ""  # 만, 억, 조
    yeo = m.group(3) or ""         # 여
    suffix = m.group(4)

    # 고유어 접미사는 항상 띄어쓰기
    space = " " if suffix in _NATIVE_SUFFIXES else ""

    # 만/억/조 또는 여가 있으면 항상 한자어
    if large_unit or yeo:
        # 일만→만, 일억→억 (1은 생략)
        sino = "" if num == 1 and large_unit else _number_to_sino(num)
        return sino + large_unit + yeo + space + suffix

    # 고유어 접미사 & 99 이하 → 고유어 사용
    if suffix in _NATIVE_SUFFIXES and num <= 99:
        native = _number_to_native(num)
        if native:
            return native + " " + suffix

    return _number_to_sino(num) + space + suffix


def _replace_decimal(m: re.Match) -> str:
    """소수점 숫자 치환 (3.5 → 삼점오)"""
    integer_part = int(m.group(1))
    decimal_digits = "".join(
        _SINO_DIGITS.get(int(d), d) for d in m.group(2)
    )
    return _number_to_sino(integer_part) + "점" + decimal_digits


def normalize_numbers_for_tts(text: str) -> str:
    """숫자를 한국어 읽기로 변환

    접미사에 따라 한자어/고유어 수사를 자동 선택합니다.

    예:
        "20여년" → "이십여년"
        "3명"   → "세 명"
        "100만" → "백만"
        "3.5"   → "삼점오"
    """
    # 소수점 (3.5 → 삼점오)
    text = re.sub(r"(\d+)\.(\d+)", _replace_decimal, text)

    # 숫자 + (만/억/조)? + 여? + 접미사
    text = re.sub(
        rf"(\d+)(만|억|조)?(여)?({_SUFFIX_RE})",
        _replace_number_suffix, text,
    )

    # 숫자 + 만/억/조 (접미사 없이)
    text = re.sub(
        r"(\d+)(만|억|조)",
        lambda m: _number_to_sino(int(m.group(1))) + m.group(2),
        text,
    )

    # 나머지 단독 숫자 → 한자어
    text = re.sub(r"\d+", lambda m: _number_to_sino(int(m.group(0))), text)

    return text


def preprocess_text_for_tts(text: str) -> str | None:
    """TTS 합성을 위한 텍스트 전처리

    GPT-SoVITS 등 TTS 엔진이 제대로 처리하지 못하는 패턴을 변환합니다.

    Args:
        text: 원본 텍스트

    Returns:
        전처리된 텍스트, 또는 None (합성 불가능한 텍스트)
    """
    # 원본 텍스트가 의미있는 내용을 포함하는지 확인
    # 말줄임표/마침표만 있는 경우 비언어적 발성으로 대체
    meaningful_chars = re.sub(r"[.\s…,?!]+", "", text)
    if not meaningful_chars:
        # 말줄임표나 문장부호만 있는 텍스트 → 비언어적 발성
        return "음…"

    # 괄호 안의 감탄사/의성어 제거 (예: "(한숨)" -> "")
    # TTS로 읽을 필요 없는 연출 지시문
    text = re.sub(r"\([^)]+\)", "", text)

    # 연속된 마침표 및 말줄임표 → 유니코드 말줄임표(…)로 통일
    # split_text_with_pauses()에서 쉬는 시간 삽입에 활용
    text = re.sub(r"\.{2,}", "…", text)
    text = re.sub(r"…{2,}", "…", text)  # 연속 말줄임표 단일화

    # 연속된 물음표/느낌표 단순화
    text = re.sub(r"[?!]{2,}", "?", text)

    # 앞뒤 공백 및 연속 공백 정리
    text = re.sub(r"\s+", " ", text).strip()

    # 문장 시작의 쉼표/마침표 제거 (한글 마침표 포함)
    text = re.sub(r"^[,.。\s]+", "", text)

    # 연속된 쉼표 정리
    text = re.sub(r",\s*,+", ",", text)

    # 숫자를 한국어 읽기로 변환
    text = normalize_numbers_for_tts(text)

    # 전처리 후에도 빈 문자열이면 None 반환
    if not text.strip():
        return None

    return text


def split_text_for_tts(text: str, max_length: int = 50) -> list[str]:
    """텍스트를 TTS용 세그먼트로 분할

    문장 종결 부호(. ! ?)에서만 분할합니다.
    참조 텍스트(30자 이하)와 합쳐서 80자 이하가 되도록 유지합니다.

    Args:
        text: 분할할 텍스트
        max_length: 세그먼트 최대 길이 (기본 50자, 이 이상이면 쉼표로 추가 분할)

    Returns:
        분할된 텍스트 세그먼트 목록
    """
    # 문장 종결 부호(. ! ?)로만 분할
    # 종결 구분자는 캡처하여 앞 세그먼트에 붙임
    parts = re.split(r"([.!?])", text)

    segments = []
    current = ""

    i = 0
    while i < len(parts):
        part = parts[i]
        if part is None:
            i += 1
            continue

        part = part.strip()
        if not part:
            i += 1
            continue

        # 종결 구분자(. ! ?)는 이전 세그먼트에 붙임
        if part in (".", "!", "?"):
            if current:
                current += part
                # 문장이 완성되면 바로 저장 (문장 단위 유지)
                segments.append(current)
                current = ""
            i += 1
            continue

        # 새 문장 시작
        current = part
        i += 1

    # 마지막 세그먼트 저장 (종결 부호 없는 경우)
    if current:
        segments.append(current)

    # 매우 긴 세그먼트만 쉼표로 분할 (80자 초과)
    final_segments = []
    for seg in segments:
        seg = seg.strip()
        if not seg:
            continue
        if len(seg) <= max_length:
            final_segments.append(seg)
        else:
            # 쉼표로 분할 시도
            comma_parts = [p.strip() for p in seg.split(",") if p.strip()]
            if len(comma_parts) > 1:
                final_segments.extend(comma_parts)
            else:
                final_segments.append(seg)

    # 너무 짧은 세그먼트(10자 미만)는 이전 세그먼트에 병합
    MIN_SEGMENT_LENGTH = 10
    if len(final_segments) > 1:
        merged = []
        for seg in final_segments:
            if merged and len(seg) < MIN_SEGMENT_LENGTH:
                # 이전 세그먼트에 병합
                merged[-1] = merged[-1].rstrip(".!?") + " " + seg
            elif merged and len(merged[-1]) < MIN_SEGMENT_LENGTH:
                # 이전이 짧으면 현재에 병합
                merged[-1] = merged[-1].rstrip(".!?") + " " + seg
            else:
                merged.append(seg)
        final_segments = merged

    return final_segments if final_segments else [text]


# ============ 구두점 기반 휴지(pause) 분할 ============

# 구두점별 휴지 시간 (ms)
PAUSE_COMMA_MS = 250       # 쉼표 후
PAUSE_ELLIPSIS_MS = 450    # 말줄임표 후
PAUSE_SENTENCE_MS = 150    # 문장 종결(. ! ?) 후


def split_text_with_pauses(text: str, max_length: int = 50) -> list[tuple[str, int]]:
    """텍스트를 TTS용 세그먼트로 분할 (구두점 기반 휴지 포함)

    쉼표, 말줄임표, 문장 종결 부호에서 분할하고
    각 세그먼트 사이에 적절한 휴지 시간을 설정합니다.

    Args:
        text: 분할할 텍스트
        max_length: 세그먼트 최대 길이 (초과 시 추가 분할)

    Returns:
        (세그먼트 텍스트, 다음 세그먼트까지 휴지 ms) 튜플 목록.
        마지막 세그먼트의 휴지는 0.
    """
    # 쉼표, 말줄임표, 문장 종결 부호에서 분할 (구분자 캡처)
    parts = re.split(r"(,\s*|…|[.!?])", text)

    segments: list[tuple[str, int]] = []
    current = ""

    for part in parts:
        if part is None:
            continue

        stripped = part.strip()
        if not stripped:
            continue

        # 쉼표: 앞 텍스트를 세그먼트로 저장
        if re.match(r"^,\s*$", part):
            if current.strip():
                segments.append((current.strip(), PAUSE_COMMA_MS))
                current = ""
        # 말줄임표: 앞 텍스트에 붙여서 저장 (운율 힌트)
        elif stripped == "…":
            current += "…"
            if current.strip():
                segments.append((current.strip(), PAUSE_ELLIPSIS_MS))
                current = ""
        # 문장 종결 부호: 앞 텍스트에 붙여서 저장
        elif stripped in (".", "!", "?"):
            current += stripped
            if current.strip():
                segments.append((current.strip(), PAUSE_SENTENCE_MS))
                current = ""
        else:
            # 일반 텍스트
            current = (current + " " + part).strip() if current else part

    # 마지막 세그먼트
    if current.strip():
        segments.append((current.strip(), 0))

    if not segments:
        return [(text, 0)]

    # 마지막 세그먼트 휴지 제거
    last_text, _ = segments[-1]
    segments[-1] = (last_text, 0)

    # 단일 세그먼트면 분할 불필요
    if len(segments) <= 1:
        return segments

    # 너무 짧은 세그먼트(3자 미만) 병합
    MIN_SEGMENT_LEN = 3
    merged: list[tuple[str, int]] = []
    for seg_text, pause in segments:
        if merged and len(seg_text) < MIN_SEGMENT_LEN:
            # 이전 세그먼트에 병합, 큰 쪽의 휴지 유지
            prev_text, prev_pause = merged[-1]
            merged[-1] = (prev_text + " " + seg_text, max(prev_pause, pause))
        elif merged and len(merged[-1][0]) < MIN_SEGMENT_LEN:
            # 이전이 짧으면 현재에 병합
            prev_text, prev_pause = merged[-1]
            merged[-1] = (prev_text + " " + seg_text, pause)
        else:
            merged.append((seg_text, pause))
    segments = merged

    return segments if segments else [(text, 0)]
