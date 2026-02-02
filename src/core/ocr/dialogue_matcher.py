"""OCR 결과와 스토리 데이터 매칭 모듈"""

from dataclasses import dataclass
from difflib import SequenceMatcher

from ..models.story import Dialogue


@dataclass
class MatchResult:
    """매칭 결과"""
    dialogue: Dialogue
    similarity: float
    index: int  # 에피소드 내 대사 인덱스


class DialogueMatcher:
    """OCR 결과를 스토리 데이터와 매칭

    퍼지 매칭으로 OCR 오류가 있어도 정확한 대사를 찾습니다.
    """

    def __init__(self, dialogues: list[Dialogue]):
        """초기화

        Args:
            dialogues: 현재 에피소드의 대사 목록
        """
        self._dialogues = dialogues
        self._last_matched_index = -1

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """두 텍스트의 유사도 계산 (0.0 ~ 1.0)"""
        if not text1 or not text2:
            return 0.0

        # 공백/줄바꿈 정규화
        t1 = " ".join(text1.split())
        t2 = " ".join(text2.split())

        return SequenceMatcher(None, t1, t2).ratio()

    def find_best_match(
        self,
        ocr_text: str,
        min_similarity: float = 0.5,
        search_window: int = 10,
    ) -> MatchResult | None:
        """OCR 텍스트와 가장 유사한 대사 찾기

        Args:
            ocr_text: OCR로 인식된 텍스트
            min_similarity: 최소 유사도 (기본 0.5)
            search_window: 마지막 매칭 위치 기준 검색 범위

        Returns:
            매칭 결과 또는 None
        """
        if not ocr_text or not self._dialogues:
            return None

        best_match: MatchResult | None = None
        best_similarity = 0.0

        # 검색 범위 설정 (마지막 매칭 위치 근처 우선)
        if self._last_matched_index >= 0:
            start = max(0, self._last_matched_index - 2)
            end = min(len(self._dialogues), self._last_matched_index + search_window)
            search_indices = list(range(start, end))
            # 나머지 인덱스 추가 (낮은 우선순위)
            search_indices.extend(
                i for i in range(len(self._dialogues))
                if i not in search_indices
            )
        else:
            search_indices = list(range(len(self._dialogues)))

        for idx in search_indices:
            dialogue = self._dialogues[idx]
            similarity = self._calculate_similarity(ocr_text, dialogue.text)

            # 현재 위치 근처면 약간의 보너스
            if self._last_matched_index >= 0:
                distance = abs(idx - self._last_matched_index)
                if distance <= 3:
                    similarity += 0.05 * (3 - distance)  # 가까울수록 보너스
                    similarity = min(similarity, 1.0)

            if similarity > best_similarity:
                best_similarity = similarity
                best_match = MatchResult(
                    dialogue=dialogue,
                    similarity=similarity,
                    index=idx,
                )

        if best_match and best_match.similarity >= min_similarity:
            self._last_matched_index = best_match.index
            return best_match

        return None

    def find_matches(
        self,
        ocr_text: str,
        top_k: int = 3,
        min_similarity: float = 0.3,
    ) -> list[MatchResult]:
        """OCR 텍스트와 유사한 대사 상위 k개 찾기

        Args:
            ocr_text: OCR로 인식된 텍스트
            top_k: 반환할 최대 개수
            min_similarity: 최소 유사도

        Returns:
            유사도 순으로 정렬된 매칭 결과 목록
        """
        if not ocr_text or not self._dialogues:
            return []

        results = []
        for idx, dialogue in enumerate(self._dialogues):
            similarity = self._calculate_similarity(ocr_text, dialogue.text)
            if similarity >= min_similarity:
                results.append(MatchResult(
                    dialogue=dialogue,
                    similarity=similarity,
                    index=idx,
                ))

        # 유사도 내림차순 정렬
        results.sort(key=lambda r: r.similarity, reverse=True)
        return results[:top_k]

    def get_next_dialogue(self) -> Dialogue | None:
        """다음 예상 대사 반환"""
        if self._last_matched_index < 0:
            return None
        next_idx = self._last_matched_index + 1
        if next_idx < len(self._dialogues):
            return self._dialogues[next_idx]
        return None

    def reset(self) -> None:
        """매칭 상태 초기화"""
        self._last_matched_index = -1

    def set_dialogues(self, dialogues: list[Dialogue]) -> None:
        """대사 목록 변경 (에피소드 전환 시)"""
        self._dialogues = dialogues
        self._last_matched_index = -1
