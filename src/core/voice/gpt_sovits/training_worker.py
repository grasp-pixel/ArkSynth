"""GPT-SoVITS 음성 준비 워커

subprocess로 실행되어 캐릭터 음성 참조 데이터를 준비합니다.
GPT-SoVITS의 zero-shot 음성 합성을 위해 참조 오디오와 텍스트만 설정합니다.
(전체 학습 없이 사전 학습된 모델로 음성 클로닝 가능)

진행 상황은 stdout으로 JSON 형식으로 출력됩니다.
"""

import argparse
import json
import logging
import shutil
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .audio_preprocessor import AudioSegment

# 프로젝트 루트 추가
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

# 로깅 설정
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# 공통 모듈에서 import
from core.voice.gpt_sovits.reference_selector import (
    VOICE_TITLE_PRIORITY,
    EXCLUDED_VOICE_TITLES,
    get_audio_duration,
    calculate_reference_score,
    is_excluded_voice,
    select_best_references,
)


def emit_progress(stage: str, progress: float, message: str, **kwargs):
    """진행 상황을 JSON으로 출력"""
    data = {
        "type": "progress",
        "stage": stage,
        "progress": progress,
        "message": message,
        **kwargs,
    }
    print(json.dumps(data, ensure_ascii=False), flush=True)


def emit_error(message: str, error: str = ""):
    """에러를 JSON으로 출력"""
    data = {
        "type": "error",
        "message": message,
        "error": error,
    }
    print(json.dumps(data, ensure_ascii=False), flush=True)


def emit_complete(char_id: str, char_name: str, model_path: str):
    """완료를 JSON으로 출력"""
    data = {
        "type": "complete",
        "char_id": char_id,
        "char_name": char_name,
        "model_path": model_path,
    }
    print(json.dumps(data, ensure_ascii=False), flush=True)


def load_charword_transcripts(
    char_id: str,
    gamedata_path: Path,
    lang: str = "ko_KR",
) -> dict[str, dict]:
    """charword_table.json에서 대사 텍스트 로드 (스킨/이격 포함)

    공통 모듈을 사용하여 로드합니다.
    """
    from core.voice.common.charword_loader import load_charword_transcripts as _load

    # 언어 코드 변환: ko_KR -> ko
    lang_map = {"ko_KR": "ko", "ja_JP": "ja", "zh_CN": "zh", "en_US": "en"}
    language = lang_map.get(lang, "ko")

    return _load(char_id, gamedata_path, language)


def convert_to_wav(input_path: Path, output_path: Path) -> bool:
    """오디오 파일을 WAV로 변환 (32kHz 모노)"""
    try:
        result = subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(input_path),
                "-ar", "32000",
                "-ac", "1",
                str(output_path),
            ],
            capture_output=True,
            check=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        # ffmpeg 없으면 그냥 복사 (WAV인 경우)
        if input_path.suffix.lower() == ".wav":
            shutil.copy(input_path, output_path)
            return True
        return False


def preprocess_audio_with_whisper(
    char_id: str,
    audio_dir: Path,
    output_dir: Path,
    transcripts: dict[str, dict],
    min_duration: float = 3.0,
    max_duration: float = 10.0,
) -> list["AudioSegment"]:
    """Whisper 기반 오디오 전처리

    긴 오디오를 문장 단위로 분할하고 정확한 텍스트를 매핑합니다.

    Args:
        char_id: 캐릭터 ID
        audio_dir: 원본 오디오 디렉토리
        output_dir: 전처리된 오디오 출력 디렉토리
        transcripts: {voice_id: {"text": str, "title": str}} 매핑
        min_duration: 최소 세그먼트 길이
        max_duration: 최대 세그먼트 길이

    Returns:
        AudioSegment 목록
    """
    try:
        # 워커는 subprocess로 실행되므로 절대 임포트 사용
        from core.voice.gpt_sovits.audio_preprocessor import AudioPreprocessor
    except ImportError as e:
        logger.warning(f"audio_preprocessor 임포트 실패: {e}")
        emit_progress("preprocessing", 0.4, f"Whisper 사용 불가: {e}")
        return []

    emit_progress("preprocessing", 0.15, "Whisper 모델 로딩 중...")

    preprocessor = AudioPreprocessor(
        model_size="large-v3-turbo",
        language="ko",
        min_duration=min_duration,
        max_duration=max_duration,
    )

    try:
        # transcripts 형식 변환: {voice_id: {"text": ..., "title": ...}} → {voice_id: text}
        simple_transcripts = {k: v["text"] for k, v in transcripts.items()}

        def on_progress(progress: float, message: str):
            emit_progress("preprocessing", 0.15 + progress * 0.25, message)

        segments = preprocessor.preprocess_character(
            char_id=char_id,
            audio_dir=audio_dir,
            output_dir=output_dir,
            transcripts=simple_transcripts,
            on_progress=on_progress,
        )

        emit_progress("preprocessing", 0.4, f"Whisper 전처리 완료: {len(segments)}개 세그먼트")
        return segments

    except Exception as e:
        logger.error(f"Whisper 전처리 실패: {e}")
        emit_progress("preprocessing", 0.4, f"Whisper 실패: {e}")
        return []

    finally:
        preprocessor.unload_model()


def prepare_reference_audio(
    char_id: str,
    audio_dir: Path,
    output_dir: Path,
    gamedata_path: Path,
    language: str = "ko",
    min_duration: float = 3.0,
    max_duration: float = 10.0,
    ref_count: int | None = None,  # None이면 모든 유효한 오디오 사용
    use_whisper: bool = True,  # Whisper 전처리 사용 여부
) -> bool:
    """참조 오디오 준비 (다중 참조 지원)

    다양한 톤을 위해 여러 참조 오디오를 선택하고 준비합니다.
    - Whisper로 긴 오디오를 문장 단위로 분할 (선택적)
    - 텍스트가 있는 오디오만 선택
    - min_duration~max_duration 사이의 오디오 선호
    - 다양한 텍스트 길이의 오디오 선택
    - WAV 형식으로 변환

    Args:
        char_id: 캐릭터 ID
        audio_dir: 오디오 파일 디렉토리
        output_dir: 출력 디렉토리
        gamedata_path: gamedata 경로
        language: 언어
        min_duration: 최소 오디오 길이
        max_duration: 최대 오디오 길이
        ref_count: 준비할 참조 오디오 개수 (None이면 모든 유효한 오디오 사용)
        use_whisper: Whisper 전처리 사용 여부

    Returns:
        bool: 성공 여부
    """
    emit_progress("preprocessing", 0.1, "오디오 파일 수집 중...")

    # 오디오 파일 목록
    audio_files = list(audio_dir.glob("*.mp3")) + list(audio_dir.glob("*.wav"))
    if not audio_files:
        emit_error("오디오 파일이 없습니다", str(audio_dir))
        return False

    emit_progress("preprocessing", 0.12, f"{len(audio_files)}개 오디오 파일 발견")

    # 대사 텍스트 로드
    emit_progress("preprocessing", 0.13, "대사 텍스트 로드 중...")
    lang_code = "ko_KR" if language == "ko" else "ja_JP" if language == "ja" else "zh_CN"
    transcripts = load_charword_transcripts(char_id, gamedata_path, lang_code)

    if not transcripts:
        emit_error("대사 텍스트가 없습니다", f"{char_id}의 charword_table 데이터 없음")
        return False

    emit_progress("preprocessing", 0.14, f"{len(transcripts)}개 대사 텍스트 로드")

    # 출력 디렉토리 생성
    output_dir.mkdir(parents=True, exist_ok=True)

    # 전처리된 오디오 경로 (학습에서도 재사용)
    from core.voice.gpt_sovits.config import GPTSoVITSConfig
    config = GPTSoVITSConfig()
    preprocessed_dir = config.get_preprocessed_audio_path(char_id)
    preprocessed_dir.mkdir(parents=True, exist_ok=True)

    # Whisper 전처리 시도
    whisper_segments: list["AudioSegment"] = []
    if use_whisper:
        whisper_segments = preprocess_audio_with_whisper(
            char_id=char_id,
            audio_dir=audio_dir,
            output_dir=preprocessed_dir,
            transcripts=transcripts,
            min_duration=min_duration,
            max_duration=max_duration,
        )

        # 전처리 완료 로그 (텍스트는 각 WAV 옆에 .txt로 저장됨)
        if whisper_segments:
            emit_progress("preprocessing", 0.45, f"전처리 완료: {len(whisper_segments)}개 세그먼트")

    # 후보 오디오 수집
    emit_progress("preprocessing", 0.5, "참조 오디오 선택 중...")
    candidates = []

    if whisper_segments:
        # Whisper 전처리된 세그먼트 사용
        emit_progress("preprocessing", 0.5, f"Whisper 전처리 세그먼트 {len(whisper_segments)}개 사용")

        for seg in whisper_segments:
            if not seg.text:
                continue

            # 원본 voice_id에서 title 찾기
            original_transcript = transcripts.get(seg.original_voice_id, {})
            title = original_transcript.get("title", "")

            # 제외 체크
            if is_excluded_voice(title, seg.text):
                continue

            # 점수 계산
            score, is_valid_duration = calculate_reference_score(
                title, seg.text, seg.duration, min_duration, max_duration
            )

            candidate = {
                "audio": seg.audio_path,
                "text": seg.text,
                "title": title,
                "text_len": len(seg.text),
                "duration": seg.duration,
                "score": score,
                "valid_duration": is_valid_duration,
            }
            candidates.append(candidate)
    else:
        # 폴백: 원본 오디오 파일 사용
        emit_progress("preprocessing", 0.5, "원본 오디오 파일 사용 (Whisper 미사용)")

        for audio_file in audio_files:
            voice_id = audio_file.stem  # CN_001
            transcript_info = transcripts.get(voice_id, {})
            text = transcript_info.get("text", "")
            title = transcript_info.get("title", "")

            if not text:
                continue

            # 공통 함수로 제외 여부 체크
            if is_excluded_voice(title, text):
                continue

            duration = get_audio_duration(audio_file)

            # 공통 함수로 점수 계산
            score, is_valid_duration = calculate_reference_score(
                title, text, duration, min_duration, max_duration
            )

            candidate = {
                "audio": audio_file,
                "text": text,
                "title": title,
                "text_len": len(text),
                "duration": duration,
                "score": score,
                "valid_duration": is_valid_duration,
            }

            candidates.append(candidate)

    # 유효 길이 범위 후보 로그
    valid_count = sum(1 for c in candidates if c["valid_duration"])
    if valid_count > 0:
        emit_progress("preprocessing", 0.55, f"{valid_count}개 유효 길이 오디오 발견 ({min_duration}-{max_duration}초)")
    else:
        emit_progress("preprocessing", 0.55, f"경고: {min_duration}-{max_duration}초 범위 오디오 없음, 가장 근접한 길이 사용")

    if not candidates:
        emit_error("적절한 참조 오디오를 찾을 수 없습니다")
        return False

    # 공통 함수로 최적의 참조 오디오 선택
    selected = select_best_references(candidates, ref_count)

    # 선택된 대사 타이틀 목록 로그
    titles = [c.get("title", c["audio"].stem) for c in selected]
    emit_progress("preprocessing", 0.6, f"{len(selected)}개 참조 오디오 선택: {', '.join(titles[:5])}{'...' if len(titles) > 5 else ''}")

    # 점수 높은 순으로 정렬
    selected.sort(key=lambda x: x["score"], reverse=True)
    best = selected[0]

    # 참조 오디오 정보 수집 (복사 없이 preprocessed 폴더 직접 참조)
    emit_progress("preprocessing", 0.7, "참조 오디오 정보 수집 중...")

    ref_audios = []
    for c in selected:
        audio_path = c["audio"]

        # Whisper 전처리된 파일은 이미 preprocessed에 있음
        # 원본 파일은 변환 후 preprocessed에 저장
        if audio_path.suffix.lower() == ".wav" and audio_path.parent == preprocessed_dir:
            # 이미 전처리된 WAV: 그대로 사용
            ref_audios.append({
                "audio": f"preprocessed/{audio_path.name}",
                "text": c["text"],
                "text_len": c["text_len"],
                "title": c.get("title", ""),
                "score": c.get("score", 0),
            })
        else:
            # 원본 오디오: preprocessed에 변환하여 저장
            converted_path = preprocessed_dir / f"{audio_path.stem}.wav"
            text_path = preprocessed_dir / f"{audio_path.stem}.txt"
            if convert_to_wav(audio_path, converted_path):
                text_path.write_text(c["text"], encoding="utf-8")
                ref_audios.append({
                    "audio": f"preprocessed/{converted_path.name}",
                    "text": c["text"],
                    "text_len": c["text_len"],
                    "title": c.get("title", ""),
                    "score": c.get("score", 0),
                })

    emit_progress("preprocessing", 0.9, f"참조 오디오 {len(ref_audios)}개 준비 완료")

    # 모델 정보 저장 (preprocessed 폴더 직접 참조)
    info = {
        "char_id": char_id,
        "ref_audio": f"preprocessed/{best['audio'].name}",
        "ref_text": best["text"],
        "ref_audios": ref_audios,
        "ref_count": len(ref_audios),
        "language": language,
        "mode": "zero_shot",
        "whisper_preprocessed": bool(whisper_segments),
    }
    info_path = output_dir / "info.json"
    with open(info_path, "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)

    emit_progress("preprocessing", 1.0, "음성 준비 완료")
    return True


def main():
    parser = argparse.ArgumentParser(description="GPT-SoVITS 음성 준비 워커")
    parser.add_argument("--char-id", required=True, help="캐릭터 ID")
    parser.add_argument("--char-name", required=True, help="캐릭터 이름")
    parser.add_argument("--audio-dir", required=True, help="오디오 파일 디렉토리")
    parser.add_argument("--output-dir", required=True, help="출력 디렉토리")
    parser.add_argument("--gamedata-path", default="data/gamedata_yostar", help="gamedata 경로")
    parser.add_argument("--gpt-sovits-path", default="C:/GPT-SoVITS", help="GPT-SoVITS 경로 (미사용)")
    parser.add_argument("--epochs-sovits", type=int, default=8, help="SoVITS 에포크 (미사용)")
    parser.add_argument("--epochs-gpt", type=int, default=15, help="GPT 에포크 (미사용)")
    parser.add_argument("--language", default="ko", help="언어")

    args = parser.parse_args()

    audio_dir = Path(args.audio_dir)
    output_dir = Path(args.output_dir)
    gamedata_path = Path(args.gamedata_path)

    # config에서 참조 오디오 길이 설정 가져오기
    from core.voice.gpt_sovits.config import GPTSoVITSConfig
    config = GPTSoVITSConfig()

    try:
        # 참조 오디오 준비 (zero-shot 합성용)
        if not prepare_reference_audio(
            args.char_id,
            audio_dir,
            output_dir,
            gamedata_path,
            args.language,
            min_duration=config.min_ref_audio_length,
            max_duration=config.max_ref_audio_length,
            use_whisper=config.use_whisper_preprocessing,
        ):
            emit_error("음성 준비 실패")
            sys.exit(1)

        # 완료
        emit_complete(args.char_id, args.char_name, str(output_dir))

    except Exception as e:
        emit_error("예외 발생", str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
