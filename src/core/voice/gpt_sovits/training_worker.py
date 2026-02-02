"""GPT-SoVITS 음성 준비 워커

subprocess로 실행되어 캐릭터 음성 참조 데이터를 준비합니다.
GPT-SoVITS의 zero-shot 음성 합성을 위해 참조 오디오와 텍스트만 설정합니다.
(전체 학습 없이 사전 학습된 모델로 음성 클로닝 가능)

진행 상황은 stdout으로 JSON 형식으로 출력됩니다.
"""

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

# 프로젝트 루트 추가
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

# 로깅 설정
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


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
) -> dict[str, str]:
    """charword_table.json에서 대사 텍스트 로드

    Args:
        char_id: 캐릭터 ID (char_002_amiya)
        gamedata_path: gamedata_yostar 경로
        lang: 언어 코드

    Returns:
        {voice_id: text} 딕셔너리 (예: {"CN_001": "박사님, 수고하셨어요."})
    """
    charword_path = gamedata_path / lang / "gamedata" / "excel" / "charword_table.json"

    if not charword_path.exists():
        logger.warning(f"charword_table.json not found: {charword_path}")
        return {}

    try:
        with open(charword_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        result = {}
        for key, item in data.get("charWords", {}).items():
            if item.get("charId") == char_id:
                voice_id = item.get("voiceId", "")  # CN_001
                voice_text = item.get("voiceText", "")
                if voice_id and voice_text:
                    result[voice_id] = voice_text

        logger.info(f"Loaded {len(result)} transcripts for {char_id}")
        return result

    except Exception as e:
        logger.error(f"Failed to load charword_table.json: {e}")
        return {}


def get_audio_duration(audio_path: Path) -> float:
    """오디오 파일 길이 계산 (초)"""
    try:
        import wave
        with wave.open(str(audio_path), "rb") as wav_file:
            frames = wav_file.getnframes()
            rate = wav_file.getframerate()
            return frames / float(rate)
    except Exception:
        # WAV가 아니면 대략적인 추정 (ffprobe 없이)
        # MP3는 대략 파일크기/16000 정도
        try:
            size = audio_path.stat().st_size
            return size / 16000  # 대략적인 추정
        except Exception:
            return 0.0


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


def prepare_reference_audio(
    char_id: str,
    audio_dir: Path,
    output_dir: Path,
    gamedata_path: Path,
    language: str = "ko",
    min_duration: float = 3.0,
    max_duration: float = 10.0,
) -> bool:
    """참조 오디오 준비

    가장 적절한 참조 오디오를 선택하고 준비합니다.
    - 텍스트가 있는 오디오만 선택
    - 3~10초 사이의 오디오 선호
    - WAV 형식으로 변환

    Args:
        char_id: 캐릭터 ID
        audio_dir: 오디오 파일 디렉토리
        output_dir: 출력 디렉토리
        gamedata_path: gamedata 경로
        language: 언어
        min_duration: 최소 오디오 길이
        max_duration: 최대 오디오 길이

    Returns:
        bool: 성공 여부
    """
    emit_progress("preprocessing", 0.1, "오디오 파일 수집 중...")

    # 오디오 파일 목록
    audio_files = list(audio_dir.glob("*.mp3")) + list(audio_dir.glob("*.wav"))
    if not audio_files:
        emit_error("오디오 파일이 없습니다", str(audio_dir))
        return False

    emit_progress("preprocessing", 0.2, f"{len(audio_files)}개 오디오 파일 발견")

    # 대사 텍스트 로드
    emit_progress("preprocessing", 0.3, "대사 텍스트 로드 중...")
    lang_code = "ko_KR" if language == "ko" else "ja_JP" if language == "ja" else "zh_CN"
    transcripts = load_charword_transcripts(char_id, gamedata_path, lang_code)

    if not transcripts:
        emit_error("대사 텍스트가 없습니다", f"{char_id}의 charword_table 데이터 없음")
        return False

    emit_progress("preprocessing", 0.4, f"{len(transcripts)}개 대사 텍스트 로드")

    # 출력 디렉토리 생성
    output_dir.mkdir(parents=True, exist_ok=True)

    # 적절한 참조 오디오 찾기
    emit_progress("preprocessing", 0.5, "참조 오디오 선택 중...")

    best_audio = None
    best_text = None
    best_score = 0

    for audio_file in audio_files:
        voice_id = audio_file.stem  # CN_001
        text = transcripts.get(voice_id, "")

        if not text:
            continue

        # 텍스트 길이로 점수 계산 (중간 길이 선호)
        text_len = len(text)
        if text_len < 5:  # 너무 짧은 텍스트 제외
            continue

        # 오디오 길이 추정
        duration = get_audio_duration(audio_file)

        # 점수 계산: 적절한 길이 + 텍스트 길이
        score = 0
        if min_duration <= duration <= max_duration:
            score += 100  # 적절한 길이 보너스
        elif duration > 0:
            score += 50  # 길이 측정 가능

        score += min(text_len, 50)  # 텍스트 길이 (최대 50점)

        if score > best_score:
            best_score = score
            best_audio = audio_file
            best_text = text

    if not best_audio:
        # 텍스트 있는 첫 번째 파일 사용
        for audio_file in audio_files:
            voice_id = audio_file.stem
            text = transcripts.get(voice_id, "")
            if text:
                best_audio = audio_file
                best_text = text
                break

    if not best_audio or not best_text:
        emit_error("적절한 참조 오디오를 찾을 수 없습니다")
        return False

    emit_progress("preprocessing", 0.7, f"참조 오디오 선택: {best_audio.name}")

    # WAV로 변환
    ref_wav_path = output_dir / "ref.wav"
    emit_progress("preprocessing", 0.8, "오디오 변환 중...")

    if not convert_to_wav(best_audio, ref_wav_path):
        # 변환 실패 시 원본 복사 시도
        shutil.copy(best_audio, output_dir / f"ref{best_audio.suffix}")
        ref_wav_path = output_dir / f"ref{best_audio.suffix}"

    # 참조 텍스트 저장
    ref_text_path = output_dir / "ref.txt"
    ref_text_path.write_text(best_text, encoding="utf-8")

    emit_progress("preprocessing", 0.9, f"참조 텍스트: {best_text[:30]}...")

    # 모델 정보 저장
    info = {
        "char_id": char_id,
        "ref_audio": best_audio.name,
        "ref_text": best_text,
        "language": language,
        "mode": "zero_shot",  # 학습 없이 zero-shot 사용
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

    try:
        # 참조 오디오 준비 (zero-shot 합성용)
        if not prepare_reference_audio(
            args.char_id,
            audio_dir,
            output_dir,
            gamedata_path,
            args.language,
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
