"""참조 오디오 관리 공통 모듈

여러 TTS 엔진에서 사용하는 참조 오디오 선택 로직.
사전 더빙 준비(training_worker)와 실시간 TTS(api_client) 모두에서 사용합니다.
"""

import json
import logging
import random
from dataclasses import dataclass
from pathlib import Path

from .audio_utils import get_audio_duration

logger = logging.getLogger(__name__)

# 참조 오디오 선택 우선순위 (높을수록 우선)
# 자연스러운 대화 톤, 적절한 길이
VOICE_TITLE_PRIORITY = {
    # 최우선 (자연스럽고 적절한 길이)
    "신뢰도 터치": 100,
    "팀장 임명": 95,
    "팀 배치": 90,
    "어시스턴트 임명": 85,  # 길이가 긴 경우 많음
    "인사": 80,
    "터치": 75,
    # 대화류 (자연스럽지만 길이 다양)
    "대화 1": 70,
    "대화 2": 70,
    "대화 3": 70,
    "신뢰도 상승 후 대화 1": 65,
    "신뢰도 상승 후 대화 2": 65,
    "신뢰도 상승 후 대화 3": 65,
    "1차 정예화 후 대화": 60,
    "2차 정예화 후 대화": 60,
    "오퍼레이터 입사": 55,
    # 중간 우선순위
    "시설에 배치": 40,
    "타이틀": 30,
}

# 제외 목록 (전투/작전 관련 - 짧고 특수한 톤)
EXCLUDED_VOICE_TITLES = {
    "작전 실패",
    "작전 개시",
    "작전 출발",
    "작전 중 1",
    "작전 중 2",
    "작전 중 3",
    "작전 중 4",
    "작전 중",
    "배치 1",
    "배치 2",
    "오퍼레이터 선택 1",
    "오퍼레이터 선택 2",
    "3★ 작전 종료",
    "비 3★ 작전 종료",
    "고난이도 작전 종료",
    "1차 정예화 (승진)",
    "2차 정예화 (승진)",
    "작전기록 학습",  # 짧음
    "방치",  # 짧음
}

# 참조 텍스트 최소 길이 (이보다 짧으면 TTS 품질 저하)
# "하아", "음..." 같은 짧은 텍스트는 음성 특성 추출이 어려움
MIN_REF_TEXT_LENGTH = 10

# 참조 텍스트 최대 길이 (이보다 길면 prompt_text + 목표 텍스트 충돌 발생)
# GPT-SoVITS에서 참조 텍스트가 길면 합성 출력에 섞이는 문제 발생
MAX_REF_TEXT_LENGTH = 30


@dataclass
class ReferenceAudio:
    """참조 오디오 정보"""

    audio_path: Path
    text: str
    score: int
    duration: float = 0.0


class ReferenceManager:
    """참조 오디오 관리자

    TTS 엔진 공통으로 사용하는 참조 오디오 선택 로직.
    """

    def __init__(
        self,
        model_dir: Path,
        min_duration: float = 3.0,
        max_duration: float = 10.0,
    ):
        self.model_dir = model_dir
        self.min_duration = min_duration
        self.max_duration = max_duration

    def select_best(self, input_text_len: int = 20) -> ReferenceAudio | None:
        """최적의 참조 오디오 선택 (하이브리드 방식)

        Args:
            input_text_len: 입력 텍스트 길이 (길이 유사도 계산용)

        Returns:
            선택된 참조 오디오 정보 또는 None
        """
        audio_path, text, score = select_reference_hybrid(
            self.model_dir,
            input_text_len=input_text_len,
            min_duration=self.min_duration,
            max_duration=self.max_duration,
        )
        if audio_path:
            duration = get_audio_duration(audio_path)
            return ReferenceAudio(audio_path, text, score, duration)
        return None

    def select_multiple(self, count: int = 3, input_text_len: int = 20) -> list[ReferenceAudio]:
        """여러 참조 오디오 선택 (캐릭터성 향상용)

        다양한 톤과 발화 스타일을 커버하기 위해 여러 참조 샘플 반환.

        Args:
            count: 선택할 참조 개수
            input_text_len: 입력 텍스트 길이 (길이 유사도 계산용)

        Returns:
            선택된 참조 오디오 목록 (점수 내림차순)
        """
        all_refs = self.get_all_by_score()
        if not all_refs:
            # 폴백: select_best 단일 반환
            best = self.select_best(input_text_len)
            return [best] if best else []

        return all_refs[:count]

    def get_all_by_score(self, exclude_primary: Path | None = None) -> list[ReferenceAudio]:
        """점수 순으로 정렬된 모든 참조 오디오

        Args:
            exclude_primary: 제외할 기본 참조 오디오 경로

        Returns:
            참조 오디오 목록 (점수 내림차순)
        """
        refs = get_all_references_by_score(
            self.model_dir,
            exclude_primary=exclude_primary,
            min_duration=self.min_duration,
            max_duration=self.max_duration,
        )
        return [
            ReferenceAudio(audio_path, text, score, get_audio_duration(audio_path))
            for audio_path, text, score in refs
        ]

    def select_best_for_qwen3(
        self,
        optimal_min: float = 5.0,
        optimal_max: float = 15.0,
    ) -> ReferenceAudio | None:
        """Qwen3-TTS ICL용 최적 참조 오디오 선택

        텍스트 길이 대신 voiceTitle 우선순위와 오디오 길이 기반으로 선택합니다.
        ICL 모드에서는 하나의 대표 참조 오디오를 사용하므로
        가장 캐릭터성이 잘 드러나는 음성을 선택합니다.

        Args:
            optimal_min: 최적 길이 최소값 (기본 5초)
            optimal_max: 최적 길이 최대값 (기본 15초)

        Returns:
            선택된 참조 오디오 또는 None
        """
        audio_path, text, score = select_reference_for_qwen3(
            self.model_dir,
            optimal_min=optimal_min,
            optimal_max=optimal_max,
        )
        if audio_path:
            duration = get_audio_duration(audio_path)
            return ReferenceAudio(audio_path, text, score, duration)
        return None


def calculate_reference_score(
    title: str,
    text: str,
    duration: float,
    min_duration: float = 3.0,
    max_duration: float = 10.0,
) -> tuple[int, bool]:
    """참조 오디오 점수 계산

    Args:
        title: 음성 타이틀 (어시스턴트 임명, 대화 1 등)
        text: 대사 텍스트
        duration: 오디오 길이 (초)
        min_duration: 최소 유효 길이
        max_duration: 최대 유효 길이

    Returns:
        (점수, 유효 길이 여부) 튜플
    """
    # 1. voiceTitle 우선순위 (0-100)
    title_priority = VOICE_TITLE_PRIORITY.get(title, 10)  # 기본값 10

    # 2. 유효 길이 보너스 (+50)
    is_valid_duration = min_duration <= duration <= max_duration
    duration_bonus = 50 if is_valid_duration else 0

    # 3. 텍스트 길이 보너스 (최대 +20, 15~40자가 이상적)
    text_len = len(text) if text else 0
    text_bonus = min(text_len, 40) // 2

    # 4. 짧은 텍스트 페널티 (MIN_REF_TEXT_LENGTH 미만이면 큰 감점)
    # "하아", "음..." 같은 짧은 텍스트는 음성 특성 추출이 어려움
    short_text_penalty = 0
    if text_len < MIN_REF_TEXT_LENGTH:
        short_text_penalty = (MIN_REF_TEXT_LENGTH - text_len) * 20  # 부족분당 20점 감점

    # 5. 긴 텍스트 페널티 (MAX_REF_TEXT_LENGTH 초과 시 강한 페널티)
    # GPT-SoVITS에서 참조 텍스트가 길면 합성 출력 앞부분에 섞이는 문제 발생
    long_text_penalty = 0
    if text_len > MAX_REF_TEXT_LENGTH:
        long_text_penalty = (text_len - MAX_REF_TEXT_LENGTH) * 15  # 초과분에 대해 15점씩 감점

    score = title_priority + duration_bonus + text_bonus - short_text_penalty - long_text_penalty
    return score, is_valid_duration


def calculate_qwen3_reference_score(
    title: str,
    duration: float,
    optimal_min: float = 5.0,
    optimal_max: float = 15.0,
) -> tuple[int, bool]:
    """Qwen3-TTS ICL용 참조 오디오 점수 계산

    Qwen3-TTS ICL 모드는 참조 오디오의 음성 품질이 핵심입니다.
    텍스트 길이보다 voiceTitle 우선순위와 오디오 길이가 중요합니다.

    점수 구성:
    - voiceTitle 우선순위: 0-100 (신뢰도 터치=100, 기본=10)
    - 최적 길이 보너스: 5-15초=+50, 3-5초/15-20초=+25
    - 길이 정밀 보너스: 7-12초 이상적, 최대 +20

    Args:
        title: 음성 타이틀
        duration: 오디오 길이 (초)
        optimal_min: 최적 길이 최소값 (기본 5초)
        optimal_max: 최적 길이 최대값 (기본 15초)

    Returns:
        (점수, 최적 길이 여부) 튜플
    """
    # 1. voiceTitle 우선순위 (0-100)
    title_priority = VOICE_TITLE_PRIORITY.get(title, 10)

    # 2. 길이 보너스
    #   - 5-15초 범위 (최적): +50
    #   - 3-5초, 15-20초 (허용): +25
    #   - 그 외: 0
    is_optimal = optimal_min <= duration <= optimal_max
    is_acceptable = 3.0 <= duration <= 20.0

    if is_optimal:
        duration_bonus = 50
    elif is_acceptable:
        duration_bonus = 25
    else:
        duration_bonus = 0

    # 3. 길이 정밀 보너스 (7-12초가 가장 이상적, 최대 +20)
    #    중심점 9.5초에서 멀어질수록 점수 감소
    ideal_center = 9.5
    if is_acceptable:
        distance_from_ideal = abs(duration - ideal_center)
        precision_bonus = max(0, int(20 - distance_from_ideal * 2))
    else:
        precision_bonus = 0

    score = title_priority + duration_bonus + precision_bonus
    return score, is_optimal


def is_excluded_voice(title: str, text: str) -> bool:
    """제외해야 할 음성인지 확인

    Args:
        title: 음성 타이틀
        text: 대사 텍스트

    Returns:
        제외 여부
    """
    # 제외 목록 체크
    if title in EXCLUDED_VOICE_TITLES:
        return True

    # 텍스트가 너무 짧음 (MIN_REF_TEXT_LENGTH 미만)
    # "하아", "음..." 같은 짧은 텍스트는 TTS 품질 저하 원인
    if not text or len(text) < MIN_REF_TEXT_LENGTH:
        return True

    return False


def select_best_references(
    candidates: list[dict],
    ref_count: int | None = None,
) -> list[dict]:
    """최적의 참조 오디오 선택

    Args:
        candidates: 후보 목록 (각 항목은 score, valid_duration, text_len 키 포함)
        ref_count: 선택할 개수 (None이면 모든 유효한 오디오)

    Returns:
        선택된 참조 오디오 목록 (점수 높은 순)
    """
    if not candidates:
        return []

    # 유효 길이 범위 후보가 있으면 그것만 사용
    valid_duration_candidates = [c for c in candidates if c.get("valid_duration", False)]
    if valid_duration_candidates:
        candidates = valid_duration_candidates

    # ref_count가 None이면 모든 유효한 오디오 사용
    if ref_count is None:
        return sorted(candidates, key=lambda x: x.get("score", 0), reverse=True)

    # 다양한 톤을 위해 텍스트 길이 기준으로 분류
    short_texts = [c for c in candidates if c.get("text_len", 0) <= 15]
    medium_texts = [c for c in candidates if 16 <= c.get("text_len", 0) <= 30]
    long_texts = [c for c in candidates if c.get("text_len", 0) > 30]

    # 각 그룹에서 점수 높은 순으로 정렬
    short_texts.sort(key=lambda x: x.get("score", 0), reverse=True)
    medium_texts.sort(key=lambda x: x.get("score", 0), reverse=True)
    long_texts.sort(key=lambda x: x.get("score", 0), reverse=True)

    # 균형 있게 선택 (짧은:중간:긴 = 1:2:2 비율 유지)
    selected = []

    medium_quota = max(2, ref_count * 2 // 5)  # 40%
    long_quota = max(2, ref_count * 2 // 5)  # 40%
    short_quota = max(1, ref_count // 5)  # 20%

    # 중간 길이 우선 (가장 자연스러움)
    for c in medium_texts[:medium_quota]:
        if len(selected) < ref_count:
            selected.append(c)

    # 긴 텍스트 (감정 표현이 풍부)
    for c in long_texts[:long_quota]:
        if len(selected) < ref_count and c not in selected:
            selected.append(c)

    # 짧은 텍스트 (간결한 표현)
    for c in short_texts[:short_quota]:
        if len(selected) < ref_count and c not in selected:
            selected.append(c)

    # 부족하면 점수 높은 순으로 채우기
    all_sorted = sorted(candidates, key=lambda x: x.get("score", 0), reverse=True)
    for c in all_sorted:
        if len(selected) >= ref_count:
            break
        if c not in selected:
            selected.append(c)

    # 최종 정렬 (점수 높은 순)
    selected.sort(key=lambda x: x.get("score", 0), reverse=True)
    return selected


def load_reference_info(model_dir: Path) -> dict | None:
    """모델 디렉토리에서 info.json 로드

    Args:
        model_dir: 모델 디렉토리 경로

    Returns:
        info.json 내용 또는 None
    """
    info_path = model_dir / "info.json"
    if not info_path.exists():
        return None

    try:
        with open(info_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"info.json 로드 실패: {e}")
        return None


def select_reference_by_score(
    model_dir: Path,
    min_duration: float = 3.0,
    max_duration: float = 10.0,
) -> tuple[Path | None, str, int]:
    """점수 기반으로 최적의 참조 오디오 선택

    info.json의 score 정보를 활용하여 가장 높은 점수의 참조 오디오를 선택합니다.
    score가 없는 기존 info.json은 첫 번째 참조(ref.wav)를 우선 사용합니다.

    Args:
        model_dir: 모델 디렉토리 경로
        min_duration: 최소 유효 길이
        max_duration: 최대 유효 길이

    Returns:
        (참조 오디오 경로, 참조 텍스트, 점수) 튜플
    """
    info = load_reference_info(model_dir)

    # info.json에 ref_audios가 있으면 점수 기반 선택
    if info and "ref_audios" in info:
        ref_audios = info["ref_audios"]

        # score 정보가 있는지 확인 (새 버전 info.json)
        has_score = any(ref.get("score", 0) > 0 for ref in ref_audios)

        if has_score:
            # 새 버전: score 기반 선택
            best_ref = None
            best_score = -1

            for ref_info in ref_audios:
                audio_name = ref_info.get("audio", "")
                score = ref_info.get("score", 0)
                audio_path = model_dir / audio_name

                if audio_path.exists() and score > best_score:
                    # 오디오 길이 필터링
                    duration = get_audio_duration(audio_path)
                    if not (min_duration <= duration <= max_duration):
                        continue

                    # 텍스트 길이 필터링
                    text = ref_info.get("text", "")
                    text_len = ref_info.get("text_len", len(text))
                    if text_len < MIN_REF_TEXT_LENGTH:
                        continue

                    best_score = score
                    best_ref = ref_info

            if best_ref:
                audio_path = model_dir / best_ref["audio"]
                text = best_ref.get("text", "")
                return audio_path, text, best_score
        else:
            # 구 버전: 첫 번째 참조(ref.wav) 우선 사용
            # ref.wav가 가장 점수가 높은 것으로 저장되었으므로
            # 텍스트 길이 조건 만족하는 첫 번째 항목 선택
            for ref in ref_audios:
                audio_path = model_dir / ref.get("audio", "ref.wav")
                if audio_path.exists():
                    text = ref.get("text", "")
                    if len(text) >= MIN_REF_TEXT_LENGTH:
                        return audio_path, text, 100  # 기본 점수

    # 폴백: preprocessed 폴더에서 첫 번째 WAV 사용
    preprocessed_dir = model_dir / "preprocessed"
    if preprocessed_dir.exists():
        wav_files = sorted(preprocessed_dir.glob("*.wav"))
        for wav_file in wav_files:
            text_file = wav_file.with_suffix(".txt")
            duration = get_audio_duration(wav_file)
            if min_duration <= duration <= max_duration:
                text = ""
                if text_file.exists():
                    text = text_file.read_text(encoding="utf-8").strip()
                # 텍스트 길이 필터링
                if len(text) >= MIN_REF_TEXT_LENGTH:
                    return wav_file, text, 0

    # 레거시 폴백: 기존 ref.wav 사용
    ref_audio = model_dir / "ref.wav"
    ref_text_file = model_dir / "ref.txt"

    if ref_audio.exists():
        text = ""
        if ref_text_file.exists():
            text = ref_text_file.read_text(encoding="utf-8").strip()
        # 텍스트 길이 필터링 (레거시는 경고만, 반환은 함)
        if len(text) < MIN_REF_TEXT_LENGTH:
            logger.warning(f"레거시 참조 텍스트가 짧음: {len(text)}자 (최소 {MIN_REF_TEXT_LENGTH}자)")
        return ref_audio, text, 0

    return None, "", 0


def select_reference_hybrid(
    model_dir: Path,
    input_text_len: int,
    min_duration: float = 3.0,
    max_duration: float = 10.0,
    top_n: int = 4,
) -> tuple[Path | None, str, int]:
    """하이브리드 참조 오디오 선택 (점수 + 텍스트 길이 + 랜덤)

    1. 점수 상위 top_n개 후보 필터링 (품질 보장)
    2. 입력 텍스트 길이와의 유사도 가중치 적용
    3. 가중 랜덤 선택 (다양성 확보)

    Args:
        model_dir: 모델 디렉토리 경로
        input_text_len: 입력 텍스트 길이
        min_duration: 최소 유효 길이
        max_duration: 최대 유효 길이
        top_n: 점수 상위 후보 개수

    Returns:
        (참조 오디오 경로, 참조 텍스트, 점수) 튜플
    """
    info = load_reference_info(model_dir)

    if not info or "ref_audios" not in info:
        # 폴백: 기본 함수 사용
        return select_reference_by_score(model_dir, min_duration, max_duration)

    ref_audios = info["ref_audios"]
    has_score = any(ref.get("score", 0) > 0 for ref in ref_audios)

    # 유효한 참조 오디오 수집
    candidates = []
    for idx, ref_info in enumerate(ref_audios):
        audio_name = ref_info.get("audio", "")
        audio_path = model_dir / audio_name

        if not audio_path.exists():
            continue

        # 오디오 길이 필터링 (3~10초)
        duration = get_audio_duration(audio_path)
        if not (min_duration <= duration <= max_duration):
            continue

        # 텍스트 길이 필터링 (MIN_REF_TEXT_LENGTH 이상)
        text = ref_info.get("text", "")
        text_len = ref_info.get("text_len", len(text))
        if text_len < MIN_REF_TEXT_LENGTH:
            logger.debug(f"참조 오디오 제외 (텍스트 짧음): {audio_name} ({text_len}자)")
            continue

        base_score = ref_info.get("score", 0) if has_score else (100 - idx)

        candidates.append(
            {
                "audio_path": audio_path,
                "text": text,
                "base_score": base_score,
                "text_len": text_len,
            }
        )

    if not candidates:
        return select_reference_by_score(model_dir, min_duration, max_duration)

    # 1. 점수 상위 top_n개 필터링
    candidates.sort(key=lambda x: x["base_score"], reverse=True)
    top_candidates = candidates[:top_n]

    # 2. 텍스트 길이 유사도 가중치 계산
    for c in top_candidates:
        len_diff = abs(c["text_len"] - input_text_len)
        # 길이 차이가 적을수록 높은 가중치 (최대 300, base_score보다 영향력 크게)
        # 길이 차이 30자 이상이면 보너스 0
        len_bonus = max(0, 300 - len_diff * 10)

        # 긴 텍스트 페널티: MAX_REF_TEXT_LENGTH 초과 시 강한 감점
        # 일본어 등 문자 밀도가 높은 언어에서 prompt_text가 길면 합성 출력에 섞임
        text_penalty = 0
        if c["text_len"] > MAX_REF_TEXT_LENGTH:
            text_penalty = (c["text_len"] - MAX_REF_TEXT_LENGTH) * 15

        c["final_score"] = c["base_score"] + len_bonus - text_penalty

    # 3. 가중 랜덤 선택
    total_score = sum(c["final_score"] for c in top_candidates)
    if total_score <= 0:
        # final_score가 가장 높은 후보 선택 (음수여도 상대적으로 높은 것 선택)
        selected = max(top_candidates, key=lambda x: x["final_score"])
    else:
        # 가중치 기반 랜덤 선택
        rand_val = random.uniform(0, total_score)
        cumulative = 0
        selected = top_candidates[0]
        for c in top_candidates:
            cumulative += c["final_score"]
            if rand_val <= cumulative:
                selected = c
                break

    return selected["audio_path"], selected["text"], selected["base_score"]


def get_all_references_by_score(
    model_dir: Path,
    exclude_primary: Path | None = None,
    min_duration: float = 3.0,
    max_duration: float = 10.0,
) -> list[tuple[Path, str, int]]:
    """점수 순으로 정렬된 모든 참조 오디오 목록

    Args:
        model_dir: 모델 디렉토리 경로
        exclude_primary: 제외할 기본 참조 오디오 경로
        min_duration: 최소 유효 길이
        max_duration: 최대 유효 길이

    Returns:
        [(오디오 경로, 텍스트, 점수), ...] 목록 (점수 내림차순)
    """
    info = load_reference_info(model_dir)
    results = []

    if info and "ref_audios" in info:
        ref_audios = info["ref_audios"]

        # score 정보가 있는지 확인 (새 버전 info.json)
        has_score = any(ref.get("score", 0) > 0 for ref in ref_audios)

        for idx, ref_info in enumerate(ref_audios):
            audio_name = ref_info.get("audio", "")
            audio_path = model_dir / audio_name

            if not audio_path.exists():
                continue
            if exclude_primary and audio_path == exclude_primary:
                continue

            # 오디오 길이 필터링
            duration = get_audio_duration(audio_path)
            if not (min_duration <= duration <= max_duration):
                continue

            # 텍스트 길이 필터링
            text = ref_info.get("text", "")
            text_len = ref_info.get("text_len", len(text))
            if text_len < MIN_REF_TEXT_LENGTH:
                continue

            if has_score:
                # 새 버전: score 사용
                score = ref_info.get("score", 0)
            else:
                # 구 버전: 인덱스 기반 (첫 번째가 가장 높은 점수)
                score = 100 - idx

            results.append((audio_path, text, score))
    else:
        # 폴백: preprocessed 폴더에서 탐색
        preprocessed_dir = model_dir / "preprocessed"
        if preprocessed_dir.exists():
            wav_files = sorted(preprocessed_dir.glob("*.wav"))
            for i, audio_path in enumerate(wav_files):
                if exclude_primary and audio_path == exclude_primary:
                    continue

                duration = get_audio_duration(audio_path)
                if not (min_duration <= duration <= max_duration):
                    continue

                text_path = audio_path.with_suffix(".txt")
                text = ""
                if text_path.exists():
                    text = text_path.read_text(encoding="utf-8").strip()

                # 텍스트 길이 필터링
                if len(text) < MIN_REF_TEXT_LENGTH:
                    continue

                # 점수 없음 (인덱스 역순으로 우선순위)
                score = 100 - i
                results.append((audio_path, text, score))

        # 레거시 폴백: 기존 ref.wav, ref_*.wav 탐색
        if not results:
            for i in range(100):
                if i == 0:
                    audio_path = model_dir / "ref.wav"
                    text_path = model_dir / "ref.txt"
                else:
                    audio_path = model_dir / f"ref_{i}.wav"
                    text_path = model_dir / f"ref_{i}.txt"

                if not audio_path.exists():
                    continue
                if exclude_primary and audio_path == exclude_primary:
                    continue

                duration = get_audio_duration(audio_path)
                if not (min_duration <= duration <= max_duration):
                    continue

                text = ""
                if text_path.exists():
                    text = text_path.read_text(encoding="utf-8").strip()

                # 텍스트 길이 필터링
                if len(text) < MIN_REF_TEXT_LENGTH:
                    continue

                score = 100 - i
                results.append((audio_path, text, score))

    # 점수 내림차순 정렬
    results.sort(key=lambda x: x[2], reverse=True)
    return results


def select_reference_for_qwen3(
    model_dir: Path,
    optimal_min: float = 5.0,
    optimal_max: float = 15.0,
) -> tuple[Path | None, str, int]:
    """Qwen3-TTS ICL용 최적 참조 오디오 선택

    텍스트 길이와 상관없이 voiceTitle 우선순위 + 오디오 길이 기반으로 선택합니다.
    ICL 모드에서는 하나의 대표 참조 오디오를 캐싱하여 사용하므로
    가장 캐릭터성이 잘 드러나는 음성을 선택합니다.

    Args:
        model_dir: 모델 디렉토리 경로
        optimal_min: 최적 길이 최소값 (기본 5초)
        optimal_max: 최적 길이 최대값 (기본 15초)

    Returns:
        (참조 오디오 경로, 참조 텍스트, 점수) 튜플
    """
    info = load_reference_info(model_dir)
    candidates = []

    if info and "ref_audios" in info:
        ref_audios = info["ref_audios"]

        for ref_info in ref_audios:
            audio_name = ref_info.get("audio", "")
            audio_path = model_dir / audio_name

            if not audio_path.exists():
                continue

            # 제외 목록 체크
            title = ref_info.get("title", "")
            text = ref_info.get("text", "")
            if title in EXCLUDED_VOICE_TITLES:
                continue

            # 최소 텍스트 길이만 체크 (너무 짧은 "하아" 등 제외)
            if len(text) < 5:
                continue

            # 오디오 길이 (허용 범위: 3-20초)
            duration = get_audio_duration(audio_path)
            if not (3.0 <= duration <= 20.0):
                continue

            # Qwen3용 점수 계산
            score, is_optimal = calculate_qwen3_reference_score(
                title, duration, optimal_min, optimal_max
            )

            candidates.append({
                "audio_path": audio_path,
                "text": text,
                "score": score,
                "is_optimal": is_optimal,
                "duration": duration,
                "title": title,
            })

    # 폴백: preprocessed 폴더에서 탐색
    if not candidates:
        preprocessed_dir = model_dir / "preprocessed"
        if preprocessed_dir.exists():
            wav_files = sorted(preprocessed_dir.glob("*.wav"))
            for audio_path in wav_files:
                duration = get_audio_duration(audio_path)
                if not (3.0 <= duration <= 20.0):
                    continue

                text_path = audio_path.with_suffix(".txt")
                text = ""
                if text_path.exists():
                    text = text_path.read_text(encoding="utf-8").strip()

                # 최소 텍스트 길이만 체크
                if len(text) < 5:
                    continue

                # 제목 없음 → 기본 점수
                score, is_optimal = calculate_qwen3_reference_score(
                    "", duration, optimal_min, optimal_max
                )

                candidates.append({
                    "audio_path": audio_path,
                    "text": text,
                    "score": score,
                    "is_optimal": is_optimal,
                    "duration": duration,
                    "title": "",
                })

    if not candidates:
        return None, "", 0

    # 최적 길이 후보가 있으면 그것만 사용
    optimal_candidates = [c for c in candidates if c["is_optimal"]]
    if optimal_candidates:
        candidates = optimal_candidates

    # 점수 내림차순 정렬
    candidates.sort(key=lambda x: x["score"], reverse=True)

    best = candidates[0]
    logger.debug(
        f"Qwen3-TTS 참조 선택: {best['audio_path'].name} "
        f"(점수={best['score']}, 길이={best['duration']:.1f}s, 제목={best['title']})"
    )

    return best["audio_path"], best["text"], best["score"]
