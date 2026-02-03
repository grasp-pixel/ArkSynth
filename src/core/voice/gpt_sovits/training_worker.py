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
    "작전 중 1", "작전 중 2", "작전 중 3", "작전 중 4", "작전 중",
    "배치 1", "배치 2",
    "오퍼레이터 선택 1", "오퍼레이터 선택 2",
    "3★ 작전 종료", "비 3★ 작전 종료", "고난이도 작전 종료",
    "1차 정예화 (승진)", "2차 정예화 (승진)",
    "작전기록 학습",  # 짧음
    "방치",  # 짧음
}


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
    """charword_table.json에서 대사 텍스트 로드

    Args:
        char_id: 캐릭터 ID (char_002_amiya)
        gamedata_path: gamedata_yostar 경로
        lang: 언어 코드

    Returns:
        {voice_id: {"text": str, "title": str}} 딕셔너리
        예: {"CN_001": {"text": "박사님, 수고하셨어요.", "title": "어시스턴트 임명"}}
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
                voice_title = item.get("voiceTitle", "")  # 어시스턴트 임명, 대화 1 등
                if voice_id and voice_text:
                    result[voice_id] = {"text": voice_text, "title": voice_title}

        logger.info(f"Loaded {len(result)} transcripts for {char_id}")
        return result

    except Exception as e:
        logger.error(f"Failed to load charword_table.json: {e}")
        return {}


def get_audio_duration(audio_path: Path) -> float:
    """오디오 파일 길이 계산 (초)"""
    # WAV 파일
    if audio_path.suffix.lower() == ".wav":
        try:
            import wave
            with wave.open(str(audio_path), "rb") as wav_file:
                frames = wav_file.getnframes()
                rate = wav_file.getframerate()
                return frames / float(rate)
        except Exception:
            pass

    # ffprobe로 정확한 길이 측정 (MP3, WAV 등 모든 포맷)
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(audio_path),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError, subprocess.TimeoutExpired):
        pass

    # mutagen 라이브러리 시도 (설치된 경우)
    try:
        from mutagen import File as MutagenFile
        audio = MutagenFile(str(audio_path))
        if audio is not None and audio.info is not None:
            return audio.info.length
    except Exception:
        pass

    # 최후의 폴백: MP3 비트레이트 추정 (128kbps 가정)
    try:
        size = audio_path.stat().st_size
        # 128kbps = 16000 bytes/sec
        return size / 16000
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
    ref_count: int | None = None,  # None이면 모든 유효한 오디오 사용
) -> bool:
    """참조 오디오 준비 (다중 참조 지원)

    다양한 톤을 위해 여러 참조 오디오를 선택하고 준비합니다.
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

    # 모든 후보 오디오 점수 계산
    emit_progress("preprocessing", 0.5, "참조 오디오 선택 중...")

    candidates = []
    valid_duration_candidates = []  # 3-10초 범위 내 후보

    for audio_file in audio_files:
        voice_id = audio_file.stem  # CN_001
        transcript_info = transcripts.get(voice_id, {})
        text = transcript_info.get("text", "")
        title = transcript_info.get("title", "")

        if not text:
            continue

        # 제외 목록 체크
        if title in EXCLUDED_VOICE_TITLES:
            continue

        text_len = len(text)
        if text_len < 5:  # 너무 짧은 텍스트 제외
            continue

        duration = get_audio_duration(audio_file)

        # 점수 계산: 우선순위 기반
        # 1. voiceTitle 우선순위 (0-100)
        title_priority = VOICE_TITLE_PRIORITY.get(title, 10)  # 기본값 10

        # 2. 유효 길이 보너스 (+50)
        is_valid_duration = min_duration <= duration <= max_duration
        duration_bonus = 50 if is_valid_duration else 0

        # 3. 텍스트 길이 보너스 (최대 +20)
        text_bonus = min(text_len, 40) // 2

        score = title_priority + duration_bonus + text_bonus

        candidate = {
            "audio": audio_file,
            "text": text,
            "title": title,
            "text_len": text_len,
            "duration": duration,
            "score": score,
            "valid_duration": is_valid_duration,
        }

        candidates.append(candidate)
        if is_valid_duration:
            valid_duration_candidates.append(candidate)

    # 유효 길이 범위 후보가 있으면 그것만 사용
    if valid_duration_candidates:
        emit_progress("preprocessing", 0.55, f"{len(valid_duration_candidates)}개 유효 길이 오디오 발견 ({min_duration}-{max_duration}초)")
        candidates = valid_duration_candidates
    else:
        emit_progress("preprocessing", 0.55, f"경고: {min_duration}-{max_duration}초 범위 오디오 없음, 가장 근접한 길이 사용")

    if not candidates:
        # 텍스트가 없으면 모든 오디오 파일로 fallback
        emit_progress("preprocessing", 0.55, "경고: 대사 텍스트 없음, 모든 오디오로 fallback")
        for audio_file in audio_files:
            voice_id = audio_file.stem
            transcript_info = transcripts.get(voice_id, {})
            text = transcript_info.get("text", "")
            title = transcript_info.get("title", "")
            if text:
                duration = get_audio_duration(audio_file)
                is_valid = min_duration <= duration <= max_duration
                candidates.append({
                    "audio": audio_file,
                    "text": text,
                    "title": title,
                    "text_len": len(text),
                    "duration": duration,
                    "score": 100 if is_valid else 1,
                    "valid_duration": is_valid,
                })

    if not candidates:
        emit_error("적절한 참조 오디오를 찾을 수 없습니다")
        return False

    # ref_count가 None이면 모든 유효한 오디오 사용
    if ref_count is None:
        # 점수 높은 순으로 정렬하여 모든 후보 사용
        selected = sorted(candidates, key=lambda x: x["score"], reverse=True)
    else:
        # 다양한 톤을 위해 텍스트 길이 기준으로 분류
        # 짧은(5-15자), 중간(16-30자), 긴(31+자) 텍스트
        short_texts = [c for c in candidates if c["text_len"] <= 15]
        medium_texts = [c for c in candidates if 16 <= c["text_len"] <= 30]
        long_texts = [c for c in candidates if c["text_len"] > 30]

        # 각 그룹에서 점수 높은 순으로 정렬
        short_texts.sort(key=lambda x: x["score"], reverse=True)
        medium_texts.sort(key=lambda x: x["score"], reverse=True)
        long_texts.sort(key=lambda x: x["score"], reverse=True)

        # 균형 있게 선택 (짧은:중간:긴 = 1:2:2 비율 유지)
        selected = []

        # 각 그룹별 할당량 계산 (총 ref_count의 비율)
        medium_quota = max(2, ref_count * 2 // 5)  # 40%
        long_quota = max(2, ref_count * 2 // 5)    # 40%
        short_quota = max(1, ref_count // 5)       # 20%

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
        all_sorted = sorted(candidates, key=lambda x: x["score"], reverse=True)
        for c in all_sorted:
            if len(selected) >= ref_count:
                break
            if c not in selected:
                selected.append(c)

    # 선택된 대사 타이틀 목록 로그
    titles = [c.get("title", c["audio"].stem) for c in selected]
    emit_progress("preprocessing", 0.6, f"{len(selected)}개 참조 오디오 선택: {', '.join(titles[:5])}{'...' if len(titles) > 5 else ''}")

    # 첫 번째를 기본 참조로 설정 (가장 점수 높은 것)
    selected.sort(key=lambda x: x["score"], reverse=True)
    best = selected[0]

    # WAV로 변환 (다중 참조)
    emit_progress("preprocessing", 0.7, "오디오 변환 중...")

    ref_audios = []
    for i, c in enumerate(selected):
        if i == 0:
            ref_wav_path = output_dir / "ref.wav"
            ref_text_path = output_dir / "ref.txt"
        else:
            ref_wav_path = output_dir / f"ref_{i}.wav"
            ref_text_path = output_dir / f"ref_{i}.txt"

        if convert_to_wav(c["audio"], ref_wav_path):
            ref_text_path.write_text(c["text"], encoding="utf-8")
            ref_audios.append({
                "audio": ref_wav_path.name,
                "text": c["text"],
                "text_len": c["text_len"],
            })

    emit_progress("preprocessing", 0.9, f"참조 오디오 {len(ref_audios)}개 준비 완료")

    # 모델 정보 저장
    info = {
        "char_id": char_id,
        "ref_audio": best["audio"].name,
        "ref_text": best["text"],
        "ref_audios": ref_audios,
        "ref_count": len(ref_audios),
        "language": language,
        "mode": "zero_shot",
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
