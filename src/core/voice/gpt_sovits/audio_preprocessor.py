"""Whisper 기반 오디오 전처리기

GPT-SoVITS 학습용 오디오를 Faster-Whisper로 전처리합니다.
- 단어 수준 타임스탬프로 정확한 분할점 결정
- 각 세그먼트에 해당하는 텍스트만 정확히 매핑
- charword_table 텍스트와 Whisper 인식 텍스트 정렬
"""

import gc
import logging
import re
import subprocess
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)


@dataclass
class WhisperWord:
    """Whisper 단어 단위 타임스탬프"""

    word: str
    start: float
    end: float
    probability: float = 1.0

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass
class WhisperSegment:
    """Whisper 세그먼트 결과"""

    start: float
    end: float
    text: str
    words: list[WhisperWord]

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass
class AudioSegment:
    """최종 분할된 오디오 세그먼트"""

    audio_path: Path
    text: str
    duration: float
    original_voice_id: str
    segment_index: int


class AudioPreprocessor:
    """Whisper 기반 오디오 전처리기

    긴 오디오를 문장 단위로 분할하고, charword_table의 텍스트와 정렬합니다.
    GPT-SoVITS 학습에 적합한 3-10초 세그먼트를 생성합니다.

    분할 방식:
    - Whisper 단어 타임스탬프 기반
    - 문장부호에서 word.end + margin으로 분할
    - 마지막 세그먼트는 오디오 끝까지 확장
    """

    # 문장 분할 기준 문장부호
    SPLIT_PUNCTUATION = "。！？!?…."

    def __init__(
        self,
        model_size: str = "large-v3-turbo",
        language: str = "ko",
        device: str = "cuda",
        compute_type: str = "float16",
        min_duration: float = 3.0,
        max_duration: float = 10.0,  # 기본 분할 범위: 3~10초
        target_sample_rate: int = 32000,
        # 분할 설정
        end_margin_ms: int = 500,  # 세그먼트 끝 여유 (word.end + margin)
    ):
        """
        Args:
            model_size: Whisper 모델 크기
            language: 언어 코드 (ko, ja, zh, en)
            device: 장치 (cuda만 지원, CPU 폴백 없음)
            compute_type: 연산 타입 (float16, int8)
            min_duration: 최소 세그먼트 길이 (초)
            max_duration: 최대 세그먼트 길이 (초)
            target_sample_rate: 출력 샘플레이트 (GPT-SoVITS는 32kHz)
            end_margin_ms: 세그먼트 끝 여유 시간 (ms) - word.end + margin에서 분할
        """
        self.model_size = model_size
        self.language = language
        self.device = device
        self.compute_type = compute_type
        self.min_duration = min_duration
        self.max_duration = max_duration
        self.target_sample_rate = target_sample_rate

        # 분할 설정
        self.end_margin_ms = end_margin_ms

        self._model = None

    @property
    def is_loaded(self) -> bool:
        """모델 로드 여부"""
        return self._model is not None

    def load_model(self) -> None:
        """Whisper 모델 로드 (GPU 전용)"""
        if self._model is not None:
            return

        try:
            from faster_whisper import WhisperModel
        except ImportError as e:
            raise ImportError(
                "faster-whisper가 설치되어 있지 않습니다. "
                "pip install faster-whisper 또는 uv add faster-whisper를 실행하세요."
            ) from e

        logger.info(f"Whisper 모델 로딩: {self.model_size} (device={self.device})")

        try:
            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )
            logger.info("Whisper 모델 로드 완료")
        except Exception as e:
            logger.error(f"Whisper 모델 로드 실패: {e}")
            raise RuntimeError(
                f"Whisper 모델을 로드할 수 없습니다. GPU가 사용 가능한지 확인하세요.\n"
                f"오류: {e}"
            ) from e

    def unload_model(self) -> None:
        """모델 언로드 및 메모리 해제"""
        if self._model is not None:
            del self._model
            self._model = None
            gc.collect()

            # CUDA 캐시 정리
            try:
                import torch

                if torch.cuda.is_initialized():
                    torch.cuda.empty_cache()
            except Exception:
                pass

            logger.info("Whisper 모델 언로드 완료")

    def transcribe_audio(
        self,
        audio_path: Path,
        word_timestamps: bool = True,
    ) -> list[WhisperSegment]:
        """오디오 파일 전사 (단어 타임스탬프 포함)

        Args:
            audio_path: 오디오 파일 경로
            word_timestamps: 단어 단위 타임스탬프 추출 여부

        Returns:
            WhisperSegment 목록
        """
        self.load_model()

        logger.debug(f"전사 시작: {audio_path.name}")

        segments_gen, info = self._model.transcribe(
            str(audio_path),
            language=self.language,
            word_timestamps=word_timestamps,
            vad_filter=True,
            beam_size=5,
        )

        segments = []
        for seg in segments_gen:
            words = []
            if seg.words:
                for w in seg.words:
                    words.append(
                        WhisperWord(
                            word=w.word,
                            start=w.start,
                            end=w.end,
                            probability=w.probability,
                        )
                    )

            segments.append(
                WhisperSegment(
                    start=seg.start,
                    end=seg.end,
                    text=seg.text.strip(),
                    words=words,
                )
            )

        logger.debug(f"전사 완료: {len(segments)}개 세그먼트")
        return segments

    def _normalize_text(self, text: str) -> str:
        """텍스트 정규화 (공백, 문장부호 통일)"""
        text = re.sub(r"\s+", "", text)  # 공백 제거
        text = re.sub(r"[.。!！?？…]+", ".", text)  # 문장부호 통일
        return text.lower()

    def align_texts(
        self,
        whisper_text: str,
        expected_text: str,
    ) -> tuple[float, str]:
        """Whisper 텍스트와 예상 텍스트 정렬

        퍼지 매칭을 사용하여 유사도를 계산합니다.

        Args:
            whisper_text: Whisper 인식 텍스트
            expected_text: charword_table의 예상 텍스트

        Returns:
            (유사도 점수 0-1, 사용할 텍스트)
        """
        norm_whisper = self._normalize_text(whisper_text)
        norm_expected = self._normalize_text(expected_text)

        # 전체 유사도 계산
        similarity = SequenceMatcher(None, norm_whisper, norm_expected).ratio()

        # 유사도가 낮으면 expected_text 사용
        if similarity < 0.5:
            logger.warning(
                f"텍스트 정렬 신뢰도 낮음: {similarity:.2f}\n"
                f"  Whisper: {whisper_text[:50]}...\n"
                f"  Expected: {expected_text[:50]}..."
            )
            return similarity, expected_text

        return similarity, expected_text

    def find_best_matching_transcript(
        self,
        whisper_text: str,
        transcripts: dict[str, str],
        threshold: float = 0.5,
    ) -> tuple[str | None, str | None, float]:
        """Whisper 텍스트와 가장 유사한 대사 찾기

        Args:
            whisper_text: Whisper 인식 텍스트
            transcripts: {voice_id: text} 매핑
            threshold: 최소 유사도 임계값

        Returns:
            (best_voice_id, best_text, similarity) 또는 (None, None, 0) if no match
        """
        if not whisper_text or not transcripts:
            return None, None, 0.0

        norm_whisper = self._normalize_text(whisper_text)

        best_voice_id = None
        best_text = None
        best_similarity = 0.0

        for voice_id, text in transcripts.items():
            if not text:
                continue

            norm_text = self._normalize_text(text)
            similarity = SequenceMatcher(None, norm_whisper, norm_text).ratio()

            if similarity > best_similarity:
                best_similarity = similarity
                best_voice_id = voice_id
                best_text = text

        if best_similarity >= threshold:
            return best_voice_id, best_text, best_similarity

        return None, None, best_similarity

    def _find_split_points(
        self,
        segments: list[WhisperSegment],
    ) -> list[tuple[float, float, str]]:
        """분할 지점 찾기

        문장부호에서 분할하고, word.end + margin에서 자릅니다.

        Args:
            segments: Whisper 세그먼트 목록

        Returns:
            [(start, end, text), ...] 분할 정보
        """
        if not segments:
            return []

        # 모든 단어 수집
        all_words: list[WhisperWord] = []
        for seg in segments:
            all_words.extend(seg.words)

        if not all_words:
            # 단어 타임스탬프가 없으면 세그먼트 단위로 반환
            return [(seg.start, seg.end, seg.text) for seg in segments]

        split_points: list[tuple[float, float, str]] = []
        current_start = all_words[0].start
        current_text = ""

        for i, word in enumerate(all_words):
            current_text += word.word

            # 문장 끝 감지 (문장부호가 포함된 단어)
            has_punctuation = any(p in word.word for p in self.SPLIT_PUNCTUATION)
            current_duration = word.end - current_start

            should_split = False

            # 문장부호에서 분할 (최소 길이 충족 시)
            if has_punctuation and current_duration >= self.min_duration:
                should_split = True
            # 최대 길이 초과 시 강제 분할
            elif current_duration >= self.max_duration:
                should_split = True

            if should_split:
                # 분할점: 현재 단어 끝 + margin (발음 잔향 포함)
                end_margin_sec = self.end_margin_ms / 1000
                split_time = word.end + end_margin_sec

                logger.debug(
                    f"분할: {word.end:.2f}s → {split_time:.2f}s (+{self.end_margin_ms}ms)"
                )

                split_points.append((current_start, split_time, current_text.strip()))
                current_start = split_time
                current_text = ""

        # 남은 부분 처리
        if current_text.strip() and all_words:
            remaining_duration = all_words[-1].end - current_start
            # 남은 부분이 최소 길이 이상이면 추가
            if remaining_duration >= self.min_duration:
                split_points.append(
                    (current_start, all_words[-1].end, current_text.strip())
                )
            # 최소 길이 미만이면 이전 세그먼트에 병합
            elif split_points:
                prev_start, _, prev_text = split_points[-1]
                split_points[-1] = (
                    prev_start,
                    all_words[-1].end,
                    prev_text + current_text.strip(),
                )

        return split_points

    def _extract_segment(
        self,
        audio_path: Path,
        start: float,
        end: float,
        output_path: Path,
        audio_duration: float | None = None,
    ) -> bool:
        """FFmpeg로 오디오 세그먼트 추출

        GPT-SoVITS 요구사항:
        - 32kHz 샘플레이트
        - 모노 채널
        - WAV 형식

        분할점은 VAD(무음 감지)로 결정되므로 추가 패딩/오프셋 불필요.
        무음 구간 중심에서 분할하면 자연스럽게 앞뒤 무음이 포함됨.

        Args:
            audio_path: 원본 오디오 파일
            start: 시작 시간 (초)
            end: 종료 시간 (초)
            output_path: 출력 파일 경로
            audio_duration: 전체 오디오 길이 (클램핑용)
        """
        # 오디오 길이로 클램핑
        actual_end = end
        if audio_duration is not None:
            actual_end = min(end, audio_duration)

        duration = actual_end - start
        if duration <= 0:
            return False

        logger.debug(f"세그먼트 추출: {start:.2f}-{actual_end:.2f}s ({duration:.2f}s)")

        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            str(start),
            "-i",
            str(audio_path),
            "-t",
            str(duration),
            "-ar",
            str(self.target_sample_rate),
            "-ac",
            "1",
            "-acodec",
            "pcm_s16le",
            str(output_path),
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                check=True,
                creationflags=subprocess.CREATE_NO_WINDOW
                if hasattr(subprocess, "CREATE_NO_WINDOW")
                else 0,
            )
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg 오류: {e.stderr.decode() if e.stderr else str(e)}")
            return False
        except FileNotFoundError:
            logger.error("FFmpeg를 찾을 수 없습니다. FFmpeg가 설치되어 있는지 확인하세요.")
            return False

    def _get_audio_duration(self, audio_path: Path) -> float:
        """오디오 파일 길이 반환 (초)"""
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(audio_path),
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                creationflags=subprocess.CREATE_NO_WINDOW
                if hasattr(subprocess, "CREATE_NO_WINDOW")
                else 0,
            )
            return float(result.stdout.strip())
        except Exception:
            return 0.0

    def split_long_audio(
        self,
        audio_path: Path,
        expected_text: str,
        voice_id: str,
        output_dir: Path,
        transcripts_all: dict[str, str] | None = None,
    ) -> list[AudioSegment]:
        """긴 오디오를 문장 단위로 분할

        1. Whisper로 전사 및 타임스탬프 추출
        2. (검증) Whisper 결과를 전체 대사와 매칭하여 텍스트 자동 교정
        3. 문장부호에서 word.end + margin으로 분할점 결정
        4. FFmpeg로 세그먼트 추출
        5. 마지막 세그먼트는 오디오 끝까지 확장
        6. 각 WAV 파일 옆에 .txt 파일 저장

        Args:
            audio_path: 원본 오디오 경로
            expected_text: charword_table의 대사 텍스트
            voice_id: 음성 ID (CN_001 등)
            output_dir: 출력 디렉토리
            transcripts_all: 검증용 전체 대사 매핑 {voice_id: text}

        Returns:
            생성된 AudioSegment 목록
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        # 오디오 길이 확인 (클램핑용)
        audio_duration = self._get_audio_duration(audio_path)

        # Whisper 전사
        segments = self.transcribe_audio(audio_path)
        if not segments:
            logger.warning(f"전사 결과 없음: {audio_path.name}")
            return []

        # 전체 Whisper 텍스트
        whisper_text = " ".join(seg.text for seg in segments)

        # 텍스트 검증 및 자동 교정
        if transcripts_all:
            best_id, best_text, best_sim = self.find_best_matching_transcript(
                whisper_text, transcripts_all, threshold=0.5
            )
            if best_id and best_text:
                if best_id != voice_id:
                    logger.warning(
                        f"텍스트 교정: {voice_id} → {best_id} (유사도: {best_sim:.2f})\n"
                        f"  기존: {expected_text[:50]}...\n"
                        f"  교정: {best_text[:50]}..."
                    )
                    expected_text = best_text
                else:
                    logger.debug(f"텍스트 검증 통과: {voice_id} (유사도: {best_sim:.2f})")
            else:
                # 매칭 실패: 오디오와 텍스트 불일치 → 건너뛰기
                # (스킨/이격 오디오가 기본 대사 텍스트와 불일치하는 경우)
                logger.warning(
                    f"텍스트 매칭 실패, 건너뜀: {voice_id} (최고 유사도: {best_sim:.2f})\n"
                    f"  Whisper: {whisper_text[:50]}...\n"
                    f"  Expected: {expected_text[:50]}..."
                )
                return []

        # 텍스트 정렬 확인
        similarity, _ = self.align_texts(whisper_text, expected_text)
        logger.debug(f"텍스트 유사도: {similarity:.2f}")

        # 분할점 찾기 (word.end + margin)
        split_points = self._find_split_points(segments)
        if not split_points:
            logger.warning(f"분할점을 찾을 수 없음: {audio_path.name}")
            return []

        # 마지막 세그먼트의 끝을 오디오 전체 길이로 확장 (발음 잔향 포함)
        if audio_duration and split_points:
            last_start, last_end, last_text = split_points[-1]
            if last_end < audio_duration:
                split_points[-1] = (last_start, audio_duration, last_text)
                logger.debug(f"마지막 세그먼트 확장: {last_end:.2f}s → {audio_duration:.2f}s")

        # 세그먼트 추출
        results: list[AudioSegment] = []

        # 순차 매칭으로 각 세그먼트의 텍스트 결정
        whisper_texts = [text for _, _, text in split_points]
        matched_texts = self._match_segments_sequential(whisper_texts, expected_text)

        for i, (start, end, whisper_seg_text) in enumerate(split_points):
            output_path = output_dir / f"{voice_id}_{i:02d}.wav"
            text_path = output_dir / f"{voice_id}_{i:02d}.txt"

            # 세그먼트 추출 (VAD로 결정된 분할점 그대로 사용)
            if not self._extract_segment(
                audio_path, start, end, output_path,
                audio_duration=audio_duration,
            ):
                continue

            # 순차 매칭 결과 사용
            seg_text = matched_texts[i]

            # 텍스트 파일 저장 (WAV 옆에)
            text_path.write_text(seg_text, encoding="utf-8")

            # 세그먼트 길이 계산
            actual_end = min(end, audio_duration) if audio_duration else end
            segment_duration = actual_end - start

            results.append(
                AudioSegment(
                    audio_path=output_path,
                    text=seg_text,
                    duration=segment_duration,
                    original_voice_id=voice_id,
                    segment_index=i,
                )
            )

        logger.info(f"분할 완료: {audio_path.name} → {len(results)}개 세그먼트")
        return results

    def _find_best_substring(
        self,
        whisper_text: str,
        expected_text: str,
        search_start: int = 0,
    ) -> tuple[int, int, float] | None:
        """expected_text에서 whisper_text와 가장 유사한 서브스트링 찾기

        슬라이딩 윈도우 방식으로 최적 매칭 위치를 찾습니다.

        Args:
            whisper_text: 찾을 텍스트 (정규화됨)
            expected_text: 검색 대상 (정규화됨)
            search_start: 검색 시작 위치

        Returns:
            (시작 인덱스, 끝 인덱스, 유사도) 또는 None
        """
        if not whisper_text or not expected_text:
            return None

        search_text = expected_text[search_start:]
        if not search_text:
            return None

        whisper_len = len(whisper_text)
        best_start = -1
        best_end = -1
        best_similarity = 0.0

        # 윈도우 크기 범위: whisper 길이의 0.7배 ~ 1.5배
        min_window = max(1, int(whisper_len * 0.7))
        max_window = min(len(search_text), int(whisper_len * 1.5))

        for window_size in range(min_window, max_window + 1):
            for pos in range(len(search_text) - window_size + 1):
                candidate = search_text[pos : pos + window_size]
                similarity = SequenceMatcher(None, whisper_text, candidate).ratio()

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_start = search_start + pos
                    best_end = search_start + pos + window_size

        if best_similarity >= 0.5:
            return (best_start, best_end, best_similarity)

        return None

    def _extract_original_substring(
        self,
        original: str,
        norm_start: int,
        norm_end: int,
    ) -> str:
        """정규화된 인덱스를 사용해 원본 텍스트에서 부분 추출

        정규화 과정(공백/문장부호 제거)의 역변환을 수행합니다.

        Args:
            original: 원본 텍스트
            norm_start: 정규화 텍스트에서의 시작 인덱스
            norm_end: 정규화 텍스트에서의 끝 인덱스

        Returns:
            원본 텍스트의 해당 부분
        """
        # 원본 인덱스 → 정규화 인덱스 매핑 구축
        orig_to_norm: list[tuple[int, int]] = []
        norm_idx = 0

        for orig_idx, char in enumerate(original):
            # _normalize_text()와 동일한 로직: 공백 제거
            if char.isspace():
                continue
            orig_to_norm.append((orig_idx, norm_idx))
            norm_idx += 1

        # 정규화 인덱스 → 원본 인덱스 역변환
        orig_start = None
        orig_end = None

        for orig_idx, n_idx in orig_to_norm:
            if n_idx == norm_start and orig_start is None:
                orig_start = orig_idx
            if n_idx == norm_end - 1:
                orig_end = orig_idx + 1

        if orig_start is None:
            orig_start = 0
        if orig_end is None:
            orig_end = len(original)

        return original[orig_start:orig_end].strip()

    def _match_segments_sequential(
        self,
        whisper_texts: list[str],
        expected_text: str,
    ) -> list[str]:
        """Whisper 세그먼트들을 expected_text와 순차적으로 매칭

        각 세그먼트에 대해 expected_text에서 가장 유사한 연속 부분을
        순차적으로 찾아 반환합니다.

        Args:
            whisper_texts: Whisper 세그먼트 텍스트 목록 (시간순)
            expected_text: 전체 예상 텍스트

        Returns:
            각 세그먼트에 대응하는 텍스트 목록
        """
        if not whisper_texts:
            return []

        if not expected_text:
            return whisper_texts

        # 단일 세그먼트: expected_text 전체 사용
        if len(whisper_texts) == 1:
            return [expected_text]

        results: list[str] = []
        search_start = 0
        norm_expected = self._normalize_text(expected_text)

        for i, whisper_text in enumerate(whisper_texts):
            norm_whisper = self._normalize_text(whisper_text)

            # 마지막 세그먼트: 남은 텍스트 전체 사용
            if i == len(whisper_texts) - 1:
                remaining = self._extract_original_substring(
                    expected_text, search_start, len(norm_expected)
                )
                results.append(remaining if remaining else whisper_text)
                continue

            # expected_text의 남은 부분에서 최적 서브스트링 찾기
            best_match = self._find_best_substring(
                norm_whisper,
                norm_expected,
                search_start,
            )

            if best_match:
                match_start, match_end, similarity = best_match
                original_text = self._extract_original_substring(
                    expected_text, match_start, match_end
                )
                results.append(original_text)
                search_start = match_end
                logger.debug(
                    f"세그먼트 {i} 매칭: 유사도 {similarity:.2f}\n"
                    f"  Whisper: {whisper_text[:40]}...\n"
                    f"  Matched: {original_text[:40]}..."
                )
            else:
                # 매칭 실패: Whisper 텍스트 사용
                results.append(whisper_text)
                logger.warning(f"세그먼트 {i} 매칭 실패: {whisper_text[:50]}...")

        return results

    def process_audio_file(
        self,
        audio_path: Path,
        expected_text: str,
        voice_id: str,
        output_dir: Path,
        transcripts_all: dict[str, str] | None = None,
    ) -> list[AudioSegment]:
        """단일 오디오 파일 처리

        오디오 길이에 따라:
        - 적절한 길이 (3-10초): 그대로 복사 (텍스트 검증만)
        - 너무 긴 경우 (>10초): split_long_audio() 호출
        - 너무 짧은 경우 (<3초): 건너뜀

        Args:
            audio_path: 오디오 파일 경로
            expected_text: charword_table의 대사 텍스트
            voice_id: 음성 ID (CN_001 등)
            output_dir: 출력 디렉토리
            transcripts_all: 검증용 전체 대사 매핑 {voice_id: text}

        Returns:
            처리된 AudioSegment 목록 (빈 목록일 수 있음)
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        # 오디오 길이 확인
        duration = self._get_audio_duration(audio_path)
        if duration <= 0:
            logger.warning(f"오디오 길이를 확인할 수 없음: {audio_path.name}")
            return []

        # 너무 짧은 오디오 건너뜀
        if duration < self.min_duration:
            logger.debug(f"너무 짧음 ({duration:.1f}초): {audio_path.name}")
            return []

        # 적절한 길이: Whisper 검증 후 복사
        if duration <= self.max_duration:
            # Whisper 검증 (짧은 오디오도 텍스트 불일치 가능)
            final_text = expected_text
            if transcripts_all:
                segments = self.transcribe_audio(audio_path)
                if segments:
                    whisper_text = " ".join(seg.text for seg in segments)
                    best_id, best_text, best_sim = self.find_best_matching_transcript(
                        whisper_text, transcripts_all, threshold=0.5
                    )
                    if best_id and best_text:
                        if best_id != voice_id:
                            logger.warning(
                                f"텍스트 교정: {voice_id} → {best_id} (유사도: {best_sim:.2f})\n"
                                f"  기존: {expected_text[:50]}...\n"
                                f"  교정: {best_text[:50]}..."
                            )
                            final_text = best_text
                        else:
                            logger.debug(f"텍스트 검증 통과: {voice_id} (유사도: {best_sim:.2f})")
                    else:
                        # 매칭 실패: 오디오와 텍스트 불일치 → 건너뛰기
                        # (스킨/이격 오디오가 기본 대사 텍스트와 불일치하는 경우)
                        logger.warning(
                            f"텍스트 매칭 실패, 건너뜀: {voice_id} (최고 유사도: {best_sim:.2f})\n"
                            f"  Whisper: {whisper_text[:50]}...\n"
                            f"  Expected: {expected_text[:50]}..."
                        )
                        return []

            output_path = output_dir / f"{voice_id}.wav"
            text_path = output_dir / f"{voice_id}.txt"

            if self._extract_segment(
                audio_path, 0, duration, output_path,
                audio_duration=duration,
            ):
                # 텍스트 파일 저장 (WAV 옆에)
                text_path.write_text(final_text, encoding="utf-8")
                return [
                    AudioSegment(
                        audio_path=output_path,
                        text=final_text,
                        duration=duration,
                        original_voice_id=voice_id,
                        segment_index=0,
                    )
                ]
            return []

        # 긴 오디오: Whisper로 분할 (검증 포함)
        return self.split_long_audio(
            audio_path, expected_text, voice_id, output_dir,
            transcripts_all=transcripts_all
        )

    def preprocess_character(
        self,
        char_id: str,
        audio_dir: Path,
        output_dir: Path,
        transcripts: dict[str, str],
        on_progress: Callable[[float, str], None] | None = None,
    ) -> list[AudioSegment]:
        """캐릭터 전체 오디오 전처리

        Args:
            char_id: 캐릭터 ID
            audio_dir: 원본 오디오 디렉토리
            output_dir: 슬라이싱 출력 디렉토리
            transcripts: {voice_id: text} 매핑
            on_progress: 진행률 콜백 (0-1, 메시지)

        Returns:
            모든 처리된 AudioSegment 목록
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        # 오디오 파일 수집
        audio_files = list(audio_dir.glob("*.mp3")) + list(audio_dir.glob("*.wav"))
        total = len(audio_files)

        if total == 0:
            logger.warning(f"오디오 파일 없음: {audio_dir}")
            return []

        logger.info(f"전처리 시작: {char_id}, {total}개 파일")

        all_segments: list[AudioSegment] = []

        for i, audio_path in enumerate(audio_files):
            # 진행률 보고
            if on_progress:
                progress = (i + 1) / total
                on_progress(progress, f"전처리 중: {audio_path.name}")

            # voice_id 추출 (확장자 제거)
            voice_id = audio_path.stem

            # 텍스트 찾기
            text = transcripts.get(voice_id, "")
            if not text:
                logger.debug(f"텍스트 없음: {voice_id}")
                continue

            # 오디오 처리 (전체 대사 전달하여 Whisper 검증 활성화)
            try:
                segments = self.process_audio_file(
                    audio_path, text, voice_id, output_dir,
                    transcripts_all=transcripts
                )
                all_segments.extend(segments)
            except Exception as e:
                logger.error(f"처리 실패 ({audio_path.name}): {e}")
                continue

        logger.info(f"전처리 완료: {char_id}, {len(all_segments)}개 세그먼트 생성")
        return all_segments


def create_training_list_from_segments(
    segments: list[AudioSegment],
    output_path: Path,
    speaker_name: str,
    language: str = "ko",
) -> int:
    """AudioSegment 리스트에서 학습 리스트 생성

    Args:
        segments: AudioSegment 목록
        output_path: 출력 파일 경로
        speaker_name: 화자 이름
        language: 언어 코드

    Returns:
        생성된 항목 수
    """
    lines = []

    for seg in segments:
        if not seg.text:
            continue
        # 형식: audio_path|speaker_name|language|text
        line = f"{seg.audio_path.absolute()}|{speaker_name}|{language}|{seg.text}"
        lines.append(line)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    logger.info(f"학습 리스트 생성: {len(lines)}개 항목 → {output_path}")
    return len(lines)
