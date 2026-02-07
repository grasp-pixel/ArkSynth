"""오디오 유틸리티 공통 모듈

여러 TTS 엔진에서 사용하는 오디오 처리 유틸리티.
"""

import io
import logging
import subprocess
import wave
from pathlib import Path

logger = logging.getLogger(__name__)


def add_silence_padding(wav_data: bytes, silence_ms: int = 150) -> bytes:
    """WAV 데이터 앞에 무음 패딩 추가

    스피커 절전 모드로 인한 앞부분 잘림 방지용.

    Args:
        wav_data: 원본 WAV 데이터
        silence_ms: 추가할 무음 길이 (밀리초)

    Returns:
        무음이 추가된 WAV 데이터
    """
    try:
        # 원본 WAV 읽기
        with io.BytesIO(wav_data) as wav_in:
            with wave.open(wav_in, "rb") as wf:
                params = wf.getparams()
                frames = wf.readframes(params.nframes)

        # 무음 프레임 생성
        bytes_per_sample = params.sampwidth
        silence_samples = int(params.framerate * silence_ms / 1000)
        silence_frames = b"\x00" * (silence_samples * params.nchannels * bytes_per_sample)

        # 새 WAV 생성 (무음 + 원본)
        with io.BytesIO() as wav_out:
            with wave.open(wav_out, "wb") as wf:
                wf.setparams(params)
                wf.writeframes(silence_frames + frames)
            return wav_out.getvalue()

    except Exception as e:
        logger.warning(f"무음 패딩 추가 실패: {e}")
        return wav_data  # 실패 시 원본 반환


def concatenate_wav(
    audio_chunks: list[bytes],
    pauses_ms: list[int] | None = None,
) -> bytes | None:
    """여러 WAV 오디오를 하나로 연결

    Args:
        audio_chunks: WAV 오디오 데이터 목록
        pauses_ms: 세그먼트 사이에 삽입할 무음 길이 목록 (밀리초).
                   길이는 len(audio_chunks) - 1이어야 합니다.
                   None이면 무음 삽입 없음.

    Returns:
        연결된 WAV 오디오 데이터 또는 None
    """
    if not audio_chunks:
        return None

    if len(audio_chunks) == 1:
        return audio_chunks[0]

    try:
        # 첫 번째 청크에서 오디오 파라미터 추출
        with io.BytesIO(audio_chunks[0]) as first_buf:
            with wave.open(first_buf, "rb") as first_wav:
                params = first_wav.getparams()

        # 모든 청크의 프레임 데이터 추출
        all_frames = []
        for chunk in audio_chunks:
            with io.BytesIO(chunk) as buf:
                with wave.open(buf, "rb") as wav_file:
                    all_frames.append(wav_file.readframes(wav_file.getnframes()))

        # 하나의 WAV로 합치기 (세그먼트 사이에 무음 삽입)
        output = io.BytesIO()
        with wave.open(output, "wb") as out_wav:
            out_wav.setparams(params)
            for i, frames in enumerate(all_frames):
                out_wav.writeframes(frames)
                # 마지막 세그먼트 뒤에는 무음 삽입하지 않음
                if pauses_ms and i < len(all_frames) - 1 and i < len(pauses_ms):
                    pause = pauses_ms[i]
                    if pause > 0:
                        silence_samples = int(params.framerate * pause / 1000)
                        silence = b"\x00" * (
                            silence_samples * params.nchannels * params.sampwidth
                        )
                        out_wav.writeframes(silence)

        pause_info = ""
        if pauses_ms:
            non_zero = [p for p in pauses_ms if p > 0]
            if non_zero:
                pause_info = f" (휴지 {len(non_zero)}개, 총 {sum(non_zero)}ms)"
        logger.info(
            f"[오디오] {len(audio_chunks)}개 세그먼트 연결 완료{pause_info}"
        )
        return output.getvalue()

    except Exception as e:
        logger.error(f"[오디오] WAV 연결 실패: {e}")
        return None


def get_audio_duration(audio_path: Path) -> float:
    """오디오 파일 길이 계산 (초)

    여러 방법으로 오디오 길이를 측정합니다:
    1. WAV 파일: wave 모듈로 직접 읽기
    2. ffprobe: 모든 포맷 지원
    3. mutagen: 설치된 경우
    4. 폴백: 파일 크기 기반 추정

    Args:
        audio_path: 오디오 파일 경로

    Returns:
        오디오 길이 (초), 실패 시 0.0
    """
    # WAV 파일
    if audio_path.suffix.lower() == ".wav":
        try:
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
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
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
