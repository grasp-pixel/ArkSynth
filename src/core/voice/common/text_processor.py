"""TTS용 텍스트 전처리 공통 모듈

여러 TTS 엔진에서 사용하는 텍스트 전처리 및 분할 로직.
"""

import re


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
        return "음..."

    # 괄호 안의 감탄사/의성어 제거 (예: "(한숨)" -> "")
    # TTS로 읽을 필요 없는 연출 지시문
    text = re.sub(r"\([^)]+\)", "", text)

    # 연속된 마침표 및 말줄임표 정리 (... 또는 … -> 단일 마침표)
    # 분할 시 마침표 기준으로 나뉘므로 단일화만 수행
    text = re.sub(r"\.{2,}", ".", text)
    text = re.sub(r"…+", ".", text)  # 유니코드 말줄임표(…)도 처리

    # 연속된 물음표/느낌표 단순화
    text = re.sub(r"[?!]{2,}", "?", text)

    # 앞뒤 공백 및 연속 공백 정리
    text = re.sub(r"\s+", " ", text).strip()

    # 문장 시작의 쉼표/마침표 제거 (한글 마침표 포함)
    text = re.sub(r"^[,.。\s]+", "", text)

    # 연속된 쉼표 정리
    text = re.sub(r",\s*,+", ",", text)

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
