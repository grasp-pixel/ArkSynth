"""GPT-SoVITS Fine-tuning 워커

캐릭터 음성 모델을 학습합니다.
subprocess로 실행되며, 진행 상황을 stdout JSON으로 출력합니다.

사용법:
    python finetuning_worker.py --char-id char_002_amiya --char-name 아미야 ...
"""

import argparse
import json
import logging
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_pretrained_paths(gpt_sovits_path: Path, version: str = "v2Pro") -> dict:
    """버전별 pretrained 모델 경로 반환

    GPT-SoVITS config.py의 경로 매핑을 따릅니다.

    Args:
        gpt_sovits_path: GPT-SoVITS 설치 경로
        version: 모델 버전 (v2, v2Pro, v2ProPlus 등)

    Returns:
        {"sovits_g": Path, "sovits_d": Path, "gpt": Path, "sv": Path}
    """
    pretrained_dir = gpt_sovits_path / "GPT_SoVITS" / "pretrained_models"

    version_map = {
        "v1": {
            "sovits_g": pretrained_dir / "s2G488k.pth",
            "sovits_d": pretrained_dir / "s2D488k.pth",
            "gpt": pretrained_dir / "s1bert25hz-2kh-longer-epoch=68e-step=50232.ckpt",
        },
        "v2": {
            "sovits_g": pretrained_dir / "gsv-v2final-pretrained" / "s2G2333k.pth",
            "sovits_d": pretrained_dir / "gsv-v2final-pretrained" / "s2D2333k.pth",
            "gpt": pretrained_dir / "gsv-v2final-pretrained" / "s1bert25hz-5kh-longer-epoch=12-step=369668.ckpt",
        },
        "v2Pro": {
            "sovits_g": pretrained_dir / "v2Pro" / "s2Gv2Pro.pth",
            "sovits_d": pretrained_dir / "v2Pro" / "s2Dv2Pro.pth",
            "gpt": pretrained_dir / "s1v3.ckpt",
        },
        "v2ProPlus": {
            "sovits_g": pretrained_dir / "v2Pro" / "s2Gv2ProPlus.pth",
            "sovits_d": pretrained_dir / "v2Pro" / "s2Dv2ProPlus.pth",
            "gpt": pretrained_dir / "s1v3.ckpt",
        },
        "v3": {
            "sovits_g": pretrained_dir / "s2Gv3.pth",
            "sovits_d": pretrained_dir / "s2Dv3.pth",
            "gpt": pretrained_dir / "s1v3.ckpt",
        },
    }

    paths = version_map.get(version, version_map["v2Pro"])

    # Speaker Verification 모델 경로 추가 (v2Pro 이상)
    paths["sv"] = pretrained_dir / "sv" / "pretrained_eres2netv2w24s4ep4.ckpt"

    return paths


def emit_progress(stage: str, progress: float, message: str = "",
                  current_epoch: int = 0, total_epochs: int = 0,
                  substage: str = ""):
    """진행 상황을 JSON으로 출력"""
    data = {
        "type": "progress",
        "stage": stage,
        "progress": progress,
        "message": message,
        "current_epoch": current_epoch,
        "total_epochs": total_epochs,
        "substage": substage,
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


def emit_complete(char_id: str, char_name: str, cleaned_size: int = 0):
    """완료를 JSON으로 출력"""
    data = {
        "type": "complete",
        "char_id": char_id,
        "char_name": char_name,
        "cleaned_size": cleaned_size,  # 정리된 용량 (bytes)
    }
    print(json.dumps(data, ensure_ascii=False), flush=True)


def cleanup_training_data(output_dir: Path) -> int:
    """학습 완료 후 중간 산출물 정리

    training_data 폴더를 삭제하여 디스크 공간을 확보합니다.
    preprocessed 폴더는 참조 오디오로 사용되므로 유지합니다.

    Args:
        output_dir: 모델 출력 디렉토리

    Returns:
        정리된 용량 (bytes)
    """
    training_data_dir = output_dir / "training_data"
    cleaned_size = 0

    if training_data_dir.exists():
        # 폴더 크기 계산
        for f in training_data_dir.rglob("*"):
            if f.is_file():
                cleaned_size += f.stat().st_size

        # 폴더 삭제
        try:
            shutil.rmtree(training_data_dir)
            size_gb = cleaned_size / (1024 ** 3)
            logger.info(f"학습 중간 산출물 정리 완료: {size_gb:.2f}GB 확보")
        except Exception as e:
            logger.error(f"training_data 폴더 삭제 실패: {e}")
            cleaned_size = 0

    return cleaned_size


def load_charword_texts(gamedata_path: Path, char_id: str, language: str = "ko") -> dict[str, str]:
    """charword_table.json에서 캐릭터 대사 텍스트 로드 (스킨/이격 포함)

    공통 모듈을 사용하여 로드합니다.
    """
    from core.voice.common.charword_loader import load_charword_texts as _load

    return _load(gamedata_path, char_id, language)


def slice_audio_files_v2(
    audio_dir: Path,
    output_dir: Path,
    transcripts: dict[str, str],
    char_id: str,
    min_duration: float = 3.0,
    max_duration: float = 10.0,
    use_whisper: bool = True,
) -> tuple[list[Path], list]:
    """Whisper 기반 오디오 슬라이싱 (v2)

    Faster-Whisper를 사용하여 문장 단위로 정확하게 분할합니다.

    Args:
        audio_dir: 원본 오디오 디렉토리
        output_dir: 슬라이싱 출력 디렉토리
        transcripts: {voice_id: text} 매핑
        char_id: 캐릭터 ID
        min_duration: 최소 세그먼트 길이
        max_duration: 최대 세그먼트 길이
        use_whisper: True면 Whisper 기반 분할, False면 기존 시간 기반 분할

    Returns:
        (슬라이싱된 오디오 파일 경로 목록, AudioSegment 목록)
    """
    if not use_whisper:
        # 기존 시간 기반 분할 (폴백)
        paths = slice_audio_files(audio_dir, output_dir, min_duration, max_duration)
        return paths, []

    try:
        # 워커는 subprocess로 실행되므로 절대 임포트 사용
        from core.voice.gpt_sovits.audio_preprocessor import AudioPreprocessor
    except ImportError as e:
        logger.warning(f"audio_preprocessor 임포트 실패, 시간 기반 분할 사용: {e}")
        paths = slice_audio_files(audio_dir, output_dir, min_duration, max_duration)
        return paths, []

    emit_progress("slicing", 0.10, "Whisper 모델 로딩 중...")

    preprocessor = AudioPreprocessor(
        model_size="large-v3-turbo",
        language="ko",
        min_duration=min_duration,
        max_duration=max_duration,
    )

    try:
        def on_progress(progress: float, message: str):
            # 슬라이싱 진행률: 0.10 ~ 0.15
            emit_progress("slicing", 0.10 + progress * 0.05, message)

        segments = preprocessor.preprocess_character(
            char_id=char_id,
            audio_dir=audio_dir,
            output_dir=output_dir,
            transcripts=transcripts,
            on_progress=on_progress,
        )

        paths = [seg.audio_path for seg in segments]
        return paths, segments

    except Exception as e:
        logger.error(f"Whisper 전처리 실패: {e}")
        emit_progress("slicing", 0.10, f"Whisper 실패, 시간 기반 분할로 폴백: {e}")
        # 폴백: 기존 시간 기반 분할
        paths = slice_audio_files(audio_dir, output_dir, min_duration, max_duration)
        return paths, []

    finally:
        preprocessor.unload_model()


def slice_audio_files(audio_dir: Path, output_dir: Path,
                      min_duration: float = 3.0, max_duration: float = 10.0) -> list[Path]:
    """오디오 파일을 적절한 길이로 슬라이싱 (레거시)

    GPT-SoVITS 학습에 적합한 3-10초 세그먼트로 분할합니다.
    이미 적절한 길이인 파일은 그대로 복사합니다.

    Note: Whisper 기반 분할 실패 시 폴백으로 사용됩니다.

    Returns:
        슬라이싱된 오디오 파일 경로 목록
    """
    try:
        from pydub import AudioSegment
    except ImportError:
        emit_error("pydub 설치 필요", "pip install pydub")
        return []

    output_dir.mkdir(parents=True, exist_ok=True)
    sliced_files = []

    audio_files = list(audio_dir.glob("*.mp3")) + list(audio_dir.glob("*.wav"))
    total = len(audio_files)

    for i, audio_path in enumerate(audio_files):
        try:
            audio = AudioSegment.from_file(str(audio_path))
            duration_sec = len(audio) / 1000.0

            # 파일명에서 voice_title 추출 (확장자 제거)
            voice_title = audio_path.stem

            if min_duration <= duration_sec <= max_duration:
                # 적절한 길이: WAV로 변환하여 복사
                output_path = output_dir / f"{voice_title}.wav"
                audio = audio.set_frame_rate(32000).set_channels(1)
                audio.export(str(output_path), format="wav")
                sliced_files.append(output_path)

            elif duration_sec > max_duration:
                # 너무 긴 오디오: 분할
                segment_length = int(max_duration * 1000)  # ms
                overlap = 500  # 0.5초 오버랩

                for j, start in enumerate(range(0, len(audio), segment_length - overlap)):
                    if start + min_duration * 1000 > len(audio):
                        break
                    end = min(start + segment_length, len(audio))
                    segment = audio[start:end]

                    if len(segment) >= min_duration * 1000:
                        output_path = output_dir / f"{voice_title}_{j:02d}.wav"
                        segment = segment.set_frame_rate(32000).set_channels(1)
                        segment.export(str(output_path), format="wav")
                        sliced_files.append(output_path)

            # 너무 짧은 오디오는 건너뜀

            if (i + 1) % 10 == 0:
                emit_progress("slicing", (i + 1) / total * 0.15,
                              f"오디오 슬라이싱: {i + 1}/{total}")

        except Exception as e:
            logger.warning(f"오디오 슬라이싱 실패 ({audio_path.name}): {e}")

    logger.info(f"슬라이싱 완료: {len(sliced_files)}개 파일")
    return sliced_files


def create_training_list_v2(
    segments: list,
    output_path: Path,
    speaker_name: str,
    language: str = "ko",
) -> int:
    """AudioSegment 리스트에서 학습 리스트 생성 (v2)

    Whisper 전처리 결과를 사용하여 정확한 텍스트 매핑으로 학습 리스트를 생성합니다.

    Args:
        segments: AudioSegment 목록 (audio_preprocessor에서 생성)
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

    logger.info(f"학습 리스트 생성 (v2): {len(lines)}개 항목 → {output_path}")
    return len(lines)


def create_training_list(sliced_dir: Path, transcripts: dict[str, str],
                         output_path: Path, speaker_name: str, language: str = "ko") -> int:
    """GPT-SoVITS 학습용 .list 파일 생성 (레거시)

    형식: audio_path|speaker_name|language|text

    Note: Whisper 전처리 실패 시 폴백으로 사용됩니다.

    Returns:
        생성된 항목 수
    """
    lines = []
    sliced_files = list(sliced_dir.glob("*.wav"))

    for audio_path in sliced_files:
        # 파일명에서 voice_title 추출 (분할된 경우 _XX 제거)
        stem = audio_path.stem
        if "_" in stem and stem.rsplit("_", 1)[1].isdigit():
            voice_title = stem.rsplit("_", 1)[0]
        else:
            voice_title = stem

        # 텍스트 찾기
        text = transcripts.get(voice_title, "")
        if not text:
            logger.warning(f"텍스트 없음: {voice_title}")
            continue

        # 형식: audio_path|speaker_name|language|text
        line = f"{audio_path.absolute()}|{speaker_name}|{language}|{text}"
        lines.append(line)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    logger.info(f"학습 리스트 생성: {len(lines)}개 항목 -> {output_path}")
    return len(lines)


def run_dataset_preparation(gpt_sovits_path: Path, list_path: Path, exp_name: str,
                            opt_dir: Path, sliced_dir: Path, version: str = "v2Pro"):
    """GPT-SoVITS 데이터셋 준비 스크립트 실행

    1. 1-get-text.py: BERT 특징 추출
    2. 2-get-hubert-wav32k.py: HuBERT 특징 추출
    3. 2-get-sv.py: Speaker Verification (v2Pro)
    4. 3-get-semantic.py: 시맨틱 토큰 추출
    """
    python_exe = gpt_sovits_path / "runtime" / "python.exe"
    logger.info(f"[Dataset Prep] GPT-SoVITS path: {gpt_sovits_path}")
    logger.info(f"[Dataset Prep] Runtime python check: {python_exe} exists={python_exe.exists()}")
    if not python_exe.exists():
        python_exe = sys.executable
        logger.warning(f"[Dataset Prep] Using system python: {python_exe}")
    else:
        logger.info(f"[Dataset Prep] Using runtime python: {python_exe}")

    prepare_dir = gpt_sovits_path / "GPT_SoVITS" / "prepare_datasets"
    bert_dir = gpt_sovits_path / "GPT_SoVITS" / "pretrained_models" / "chinese-roberta-wwm-ext-large"
    pretrained_dir = gpt_sovits_path / "GPT_SoVITS" / "pretrained_models"

    # 버전별 pretrained 경로 가져오기
    pretrained = get_pretrained_paths(gpt_sovits_path, version)

    # 출력 디렉토리 생성
    opt_dir.mkdir(parents=True, exist_ok=True)

    # 환경 변수 설정
    env = os.environ.copy()
    # PYTHONPATH 설정 (GPT_SoVITS 모듈 + 루트의 tools 모듈)
    gpt_sovits_dir = str(gpt_sovits_path / "GPT_SoVITS")
    root_dir = str(gpt_sovits_path)  # tools 폴더가 여기 있음
    existing_pythonpath = env.get("PYTHONPATH", "")
    pythonpath_parts = [gpt_sovits_dir, root_dir]
    if existing_pythonpath:
        pythonpath_parts.append(existing_pythonpath)
    env["PYTHONPATH"] = ";".join(pythonpath_parts)

    # s2 config 파일 생성 (3-get-semantic.py에서 필요)
    # 기본 템플릿 로드
    config_template_path = gpt_sovits_path / "GPT_SoVITS" / "configs" / f"s2{version}.json"
    if not config_template_path.exists():
        # 버전별 템플릿이 없으면 기본 템플릿 사용
        config_template_path = gpt_sovits_path / "GPT_SoVITS" / "configs" / "s2.json"

    if config_template_path.exists():
        with open(config_template_path, "r", encoding="utf-8") as f:
            s2_config = json.load(f)
    else:
        # 템플릿이 없으면 기본 구조 생성
        s2_config = {
            "train": {
                "segment_size": 20480,
                "seed": 1234,
            },
            "data": {
                "n_speakers": 300,
            },
            "model": {},
        }

    # 필수 필드 업데이트
    s2_config["train"]["exp_dir"] = str(opt_dir.absolute())
    s2_config["data"]["exp_dir"] = str(opt_dir.absolute())
    s2_config["data"]["max_wav_value"] = 32768.0
    s2_config["data"]["sampling_rate"] = 32000
    s2_config["data"]["filter_length"] = 2048
    s2_config["data"]["hop_length"] = 640
    s2_config["data"]["win_length"] = 2048
    s2_config["data"]["n_mel_channels"] = 128
    s2_config["s2_ckpt_dir"] = str(opt_dir / f"logs_s2_{version}")
    s2_config["pretrained_s2G"] = str(pretrained["sovits_g"])
    s2_config["pretrained_s2D"] = str(pretrained["sovits_d"])
    s2_config["content_module"] = "cnhubert"

    s2config_path = opt_dir / "s2_config.json"
    with open(s2config_path, "w", encoding="utf-8") as f:
        json.dump(s2_config, f, ensure_ascii=False, indent=2)

    env.update({
        "inp_text": str(list_path.absolute()),
        "inp_wav_dir": str(sliced_dir.absolute()),
        "exp_name": exp_name,
        "opt_dir": str(opt_dir.absolute()),
        "bert_pretrained_dir": str(bert_dir.absolute()),
        "cnhubert_base_dir": str((pretrained_dir / "chinese-hubert-base").absolute()),
        "pretrained_s2G": str(pretrained["sovits_g"].absolute()),
        "s2config_path": str(s2config_path.absolute()),
        "sv_path": str(pretrained["sv"].absolute()),  # Speaker Verification 모델 경로
        "i_part": "0",
        "all_parts": "1",
        "_CUDA_VISIBLE_DEVICES": "0",
        "is_half": "True",
        "version": version,
    })

    scripts = [
        ("1-get-text.py", "BERT 특징 추출", 0.25),
        ("2-get-hubert-wav32k.py", "HuBERT 특징 추출", 0.50),
        ("3-get-semantic.py", "시맨틱 토큰 추출", 0.75),
    ]

    # v2Pro인 경우 2-get-sv.py 추가
    if "v2" in version.lower():
        scripts.insert(2, ("2-get-sv.py", "Speaker Verification", 0.60))
        # 진행률 재조정
        scripts = [
            ("1-get-text.py", "BERT 특징 추출", 0.25),
            ("2-get-hubert-wav32k.py", "HuBERT 특징 추출", 0.45),
            ("2-get-sv.py", "Speaker Verification", 0.60),
            ("3-get-semantic.py", "시맨틱 토큰 추출", 0.75),
        ]

    # sys.path 설정을 위한 preamble (embedded Python은 PYTHONPATH 무시)
    eres2net_dir = str(gpt_sovits_path / "GPT_SoVITS" / "eres2net")
    syspath_preamble = f"""
import sys
sys.path.insert(0, r'{gpt_sovits_dir}')
sys.path.insert(0, r'{root_dir}')
sys.path.insert(0, r'{eres2net_dir}')
"""

    for script_name, stage_name, progress in scripts:
        script_path = prepare_dir / script_name
        if not script_path.exists():
            logger.warning(f"스크립트 없음: {script_path}")
            continue

        emit_progress("preparing", 0.15 + progress * 0.25,
                      f"데이터셋 준비: {stage_name}", substage=stage_name)

        try:
            # -c 옵션으로 sys.path 수정 후 스크립트 실행 (절대 경로 사용)
            # cwd는 루트 디렉토리로 설정 (스크립트가 GPT_SoVITS/eres2net 경로를 기대)
            abs_script_path = script_path.absolute()
            exec_code = f"{syspath_preamble}\nexec(open(r'{abs_script_path}', encoding='utf-8').read())"
            result = subprocess.run(
                [str(python_exe), "-c", exec_code],
                env=env,
                cwd=str(gpt_sovits_path),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            if result.returncode != 0:
                error_msg = result.stderr or result.stdout or "알 수 없는 에러"
                # 마지막 10줄만 로깅
                error_lines = error_msg.strip().split("\n")[-10:]
                logger.error(f"{script_name} 실패:\n" + "\n".join(error_lines))

                # 3-get-semantic.py는 필수 스크립트
                if script_name == "3-get-semantic.py":
                    emit_error(f"{script_name} 실패", "\n".join(error_lines))
                    return False
            else:
                logger.info(f"{script_name} 완료")

        except Exception as e:
            logger.error(f"{script_name} 실행 오류: {e}")
            if script_name == "3-get-semantic.py":
                emit_error(f"{script_name} 실행 오류", str(e))
                return False

    return True


def merge_partition_files(opt_dir: Path):
    """파티션 파일들을 합쳐서 최종 파일 생성

    GPT-SoVITS는 파티션별로 파일을 생성합니다 (예: 2-name2text-0.txt).
    이 함수는 모든 파티션 파일을 합쳐서 최종 파일을 생성합니다.
    """
    # 2-name2text-{i}.txt → 2-name2text.txt
    name2text_files = sorted(opt_dir.glob("*-name2text-*.txt"))
    if name2text_files:
        final_path = opt_dir / "2-name2text.txt"
        with open(final_path, "w", encoding="utf-8") as out:
            for f in name2text_files:
                with open(f, "r", encoding="utf-8") as inp:
                    out.write(inp.read())
        logger.info(f"name2text 합침: {len(name2text_files)}개 → {final_path}")

    # 6-name2semantic-{i}.tsv → 6-name2semantic.tsv
    semantic_files = sorted(opt_dir.glob("*-name2semantic-*.tsv"))
    if semantic_files:
        final_path = opt_dir / "6-name2semantic.tsv"
        with open(final_path, "w", encoding="utf-8") as out:
            for f in semantic_files:
                with open(f, "r", encoding="utf-8") as inp:
                    out.write(inp.read())
        logger.info(f"name2semantic 합침: {len(semantic_files)}개 → {final_path}")


def verify_dataset_preparation(opt_dir: Path, version: str = "v2Pro",
                               language: str = "ko") -> tuple[bool, str]:
    """데이터셋 준비 결과 검증

    Args:
        opt_dir: 데이터셋 준비 출력 디렉토리
        version: 모델 버전
        language: 언어 코드 (zh의 경우 BERT 필수)

    Returns:
        (성공 여부, 메시지) 튜플
    """
    # 먼저 파티션 파일들을 합침
    merge_partition_files(opt_dir)

    required_files = {
        "2-name2text.txt": opt_dir / "2-name2text.txt",
        "6-name2semantic.tsv": opt_dir / "6-name2semantic.tsv",
    }

    # 필수 디렉토리
    required_dirs = {
        "4-cnhubert": opt_dir / "4-cnhubert",
        "5-wav32k": opt_dir / "5-wav32k",
    }

    # BERT는 중국어에서만 필수 (chinese-roberta-wwm-ext-large는 중국어 전용)
    if language == "zh":
        required_dirs["3-bert"] = opt_dir / "3-bert"

    # v2Pro 이상에서는 sv 디렉토리도 필요
    if version.startswith("v2Pro"):
        required_dirs["7-sv_cn"] = opt_dir / "7-sv_cn"

    missing = []

    # 필수 파일 확인
    for name, path in required_files.items():
        if not path.exists():
            # 파티션 파일 확인
            pattern = name.replace(".txt", "-*.txt").replace(".tsv", "-*.tsv")
            partition_files = list(opt_dir.glob(pattern))
            if not partition_files:
                missing.append(f"파일 없음: {name}")
        elif path.stat().st_size == 0:
            missing.append(f"빈 파일: {name}")

    # 필수 디렉토리 확인
    for name, path in required_dirs.items():
        if not path.exists():
            missing.append(f"디렉토리 없음: {name}")
        elif not any(path.iterdir()):
            missing.append(f"빈 디렉토리: {name}")

    if missing:
        return False, "; ".join(missing)

    return True, "OK"


def run_sovits_training(gpt_sovits_path: Path, exp_name: str, opt_dir: Path,
                        epochs: int = 8, batch_size: int = 4, save_every_epoch: bool = True,
                        version: str = "v2Pro"):
    """SoVITS 모델 학습 (s2_train.py)"""
    python_exe = gpt_sovits_path / "runtime" / "python.exe"
    if not python_exe.exists():
        python_exe = sys.executable

    train_script = gpt_sovits_path / "GPT_SoVITS" / "s2_train.py"

    # 버전별 pretrained 경로 가져오기
    pretrained = get_pretrained_paths(gpt_sovits_path, version)

    # 필수 파일 검증
    if not train_script.exists():
        emit_error("SoVITS 학습 스크립트 없음", f"s2_train.py를 찾을 수 없습니다: {train_script}")
        return False

    if not pretrained["sovits_g"].exists() or not pretrained["sovits_d"].exists():
        emit_error("Pretrained 모델 없음",
                   f"s2G/s2D 모델을 찾을 수 없습니다: {pretrained['sovits_g']}, {pretrained['sovits_d']}")
        return False

    # 출력 디렉토리 생성
    # s2_train.py는 logs_s2_{version} 형식을 사용 (예: logs_s2_v2Pro)
    opt_dir.mkdir(parents=True, exist_ok=True)
    s2_ckpt_dir = opt_dir / f"logs_s2_{version}"
    s2_ckpt_dir.mkdir(parents=True, exist_ok=True)
    sovits_weight_dir = opt_dir / f"SoVITS_weights_{version}"
    sovits_weight_dir.mkdir(parents=True, exist_ok=True)

    # s2 config 생성 - 템플릿에서 로드
    config_template_path = gpt_sovits_path / "GPT_SoVITS" / "configs" / f"s2{version}.json"
    if not config_template_path.exists():
        config_template_path = gpt_sovits_path / "GPT_SoVITS" / "configs" / "s2.json"

    if config_template_path.exists():
        with open(config_template_path, "r", encoding="utf-8") as f:
            s2_config = json.load(f)
    else:
        # 템플릿이 없으면 기본 구조 생성 (필수 필드 포함)
        s2_config = {
            "train": {
                "segment_size": 20480,
                "seed": 1234,
                "learning_rate": 0.0001,
                "betas": [0.8, 0.99],
                "eps": 1e-9,
                "fp16_run": True,
                "lr_decay": 0.999875,
            },
            "data": {
                "n_speakers": 300,
            },
            "model": {},
        }

    # 필수 필드 덮어쓰기
    s2_config["train"]["exp_dir"] = str(opt_dir.absolute())
    s2_config["train"]["epochs"] = epochs
    s2_config["train"]["batch_size"] = batch_size
    s2_config["train"]["save_every_epoch"] = save_every_epoch
    s2_config["train"]["if_save_latest"] = True
    s2_config["train"]["if_save_every_weights"] = save_every_epoch
    s2_config["train"]["gpu_numbers"] = "0"
    # pretrained 모델 경로는 train 섹션에 있어야 함 (s2_train.py가 hps.train.pretrained_s2G 참조)
    s2_config["train"]["pretrained_s2G"] = str(pretrained["sovits_g"].absolute())
    s2_config["train"]["pretrained_s2D"] = str(pretrained["sovits_d"].absolute())

    s2_config["data"]["exp_dir"] = str(opt_dir.absolute())
    s2_config["data"]["max_wav_value"] = 32768.0
    s2_config["data"]["sampling_rate"] = 32000
    s2_config["data"]["filter_length"] = 2048
    s2_config["data"]["hop_length"] = 640
    s2_config["data"]["win_length"] = 2048
    s2_config["data"]["n_mel_channels"] = 128
    s2_config["data"]["mel_fmin"] = 0.0
    s2_config["data"]["mel_fmax"] = None

    s2_config["model"]["version"] = version
    s2_config["s2_ckpt_dir"] = str(s2_ckpt_dir.absolute())
    s2_config["save_weight_dir"] = str(sovits_weight_dir.absolute())
    s2_config["name"] = exp_name
    s2_config["version"] = version

    config_path = opt_dir / "s2_config.json"
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(s2_config, f, ensure_ascii=False, indent=2)

    emit_progress("sovits_training", 0.40, f"SoVITS 학습 시작 (에포크: {epochs})")
    logger.info(f"[SoVITS] 학습 시작 - 에포크: {epochs}, 배치: {batch_size}, 버전: {version}")

    env = os.environ.copy()
    # PYTHONPATH 설정 (GPT_SoVITS 모듈 + 루트의 tools/utils 모듈)
    gpt_sovits_dir = str(gpt_sovits_path / "GPT_SoVITS")
    root_dir = str(gpt_sovits_path)

    # sys.path 설정 후 runpy로 스크립트 실행 (multiprocessing 호환)
    # 절대 경로로 변환 (cwd가 다른 디렉토리로 설정되므로)
    abs_config_path = config_path.absolute()
    abs_train_script = train_script.absolute()
    wrapper_code = f"""
import sys
sys.path.insert(0, r'{gpt_sovits_dir}')
sys.path.insert(0, r'{root_dir}')
sys.argv = ['s2_train.py', '-c', r'{abs_config_path}']
import runpy
runpy.run_path(r'{abs_train_script}', run_name='__main__')
"""

    try:
        process = subprocess.Popen(
            [str(python_exe), "-c", wrapper_code],
            cwd=str(gpt_sovits_path / "GPT_SoVITS"),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )

        current_epoch = 0
        last_lines = []  # 마지막 출력 라인들 (에러 진단용)
        max_lines = 20
        line_count = 0
        last_progress_time = 0
        import time as time_module

        for line in iter(process.stdout.readline, ""):
            line = line.strip()
            if not line:
                continue

            line_count += 1

            # 에러 진단용 마지막 라인 저장
            last_lines.append(line)
            if len(last_lines) > max_lines:
                last_lines.pop(0)

            # 에포크 진행 파싱 (다양한 형식 지원)
            epoch_parsed = False
            step_parsed = False

            # 형식 1: "Epoch 1/8" 또는 "Epoch 1: 100%"
            if "Epoch" in line:
                try:
                    import re
                    # "Epoch X/Y" 형식
                    match = re.search(r"Epoch\s*(\d+)\s*/\s*(\d+)", line)
                    if match:
                        current_epoch = int(match.group(1))
                        total = int(match.group(2))
                        epoch_parsed = True
                    else:
                        # "Epoch X:" 형식 (PyTorch Lightning)
                        match = re.search(r"Epoch\s*(\d+)\s*:", line)
                        if match:
                            current_epoch = int(match.group(1)) + 1  # 0-indexed → 1-indexed
                            total = epochs  # 함수 파라미터 사용
                            epoch_parsed = True

                    if epoch_parsed:
                        progress = 0.40 + (current_epoch / total) * 0.20
                        emit_progress("sovits_training", progress,
                                      f"SoVITS 학습 중: 에포크 {current_epoch}/{total}",
                                      current_epoch=current_epoch, total_epochs=total)
                        logger.info(f"[SoVITS] 에포크 {current_epoch}/{total}")
                except Exception as e:
                    logger.warning(f"[SoVITS] 에포크 파싱 실패: {e}")

            # Step 파싱 (에포크 없이 스텝만 출력하는 경우)
            elif "step" in line.lower() or "steps" in line.lower():
                try:
                    import re
                    match = re.search(r"(\d+)\s*/\s*(\d+)\s*(?:step|steps)", line.lower())
                    if match:
                        current_step = int(match.group(1))
                        total_steps = int(match.group(2))
                        step_parsed = True
                        # 스텝 기반 진행률 (40% ~ 60%)
                        step_progress = current_step / total_steps if total_steps > 0 else 0
                        progress = 0.40 + step_progress * 0.20
                        # 10% 단위로만 업데이트
                        if int(step_progress * 10) != int(last_progress_time):
                            last_progress_time = int(step_progress * 10)
                            emit_progress("sovits_training", progress,
                                          f"SoVITS 학습 중: 스텝 {current_step}/{total_steps}")
                except Exception:
                    pass

            # 5초마다 heartbeat 진행 업데이트 (학습 중임을 알림)
            current_time = time_module.time()
            if line_count % 50 == 0 and not epoch_parsed and not step_parsed:
                emit_progress("sovits_training", 0.40 + (current_epoch / epochs) * 0.20 if current_epoch > 0 else 0.41,
                              f"SoVITS 학습 진행 중... (라인 {line_count})")

            # 중요 로그만 출력 (과다 로그 방지)
            is_important = (
                epoch_parsed or
                "error" in line.lower() or
                "warning" in line.lower() or
                "saved" in line.lower() or
                "checkpoint" in line.lower() or
                line.startswith("INFO:__main__:")
            )
            if is_important:
                logger.info(f"[SoVITS] {line}")
            elif line_count <= 10 or line_count % 100 == 0:
                # 처음 10줄과 100줄마다만 출력
                logger.debug(f"[SoVITS] {line}")

        process.wait()
        if process.returncode != 0:
            error_detail = "\n".join(last_lines[-10:]) if last_lines else "출력 없음"
            emit_error("SoVITS 학습 실패", f"exit code: {process.returncode}\n{error_detail}")
            return False

    except Exception as e:
        emit_error("SoVITS 학습 오류", str(e))
        return False

    return True


def run_gpt_training(gpt_sovits_path: Path, exp_name: str, opt_dir: Path,
                     epochs: int = 15, batch_size: int = 4, save_every_epoch: bool = True,
                     version: str = "v2Pro"):
    """GPT 모델 학습 (s1_train.py)"""
    python_exe = gpt_sovits_path / "runtime" / "python.exe"
    if not python_exe.exists():
        python_exe = sys.executable

    train_script = gpt_sovits_path / "GPT_SoVITS" / "s1_train.py"

    # 버전별 pretrained 경로 가져오기
    pretrained = get_pretrained_paths(gpt_sovits_path, version)

    # 필수 파일 검증
    if not train_script.exists():
        emit_error("GPT 학습 스크립트 없음", f"s1_train.py를 찾을 수 없습니다: {train_script}")
        return False

    if not pretrained["gpt"].exists():
        emit_error("Pretrained GPT 모델 없음", f"s1 모델을 찾을 수 없습니다: {pretrained['gpt']}")
        return False

    # 출력 디렉토리 생성
    opt_dir.mkdir(parents=True, exist_ok=True)
    gpt_weight_dir = opt_dir / f"GPT_weights_{version}"
    gpt_weight_dir.mkdir(parents=True, exist_ok=True)
    (opt_dir / f"logs_s1_{version}").mkdir(parents=True, exist_ok=True)

    # GPT config 생성 (YAML 형식)
    # 모든 경로를 절대 경로로 변환 (cwd가 다른 디렉토리로 설정되므로)
    s1_config = {
        "train": {
            "seed": 1234,
            "epochs": epochs,
            "batch_size": batch_size,
            "save_every_n_epoch": 1 if save_every_epoch else epochs,
            "if_save_latest": True,
            "if_save_every_weights": save_every_epoch,
            "half_weights_save_dir": str(gpt_weight_dir.absolute()),
            "exp_name": exp_name,
            "precision": "16-mixed",  # PyTorch Lightning precision
            "gradient_clip": 1.0,
        },
        "data": {
            "max_eval_sample": 8,
            "max_sec": 54,
            "num_workers": 4,
            "pad_val": 1024,
        },
        "model": {
            "vocab_size": 1025,
            "phoneme_vocab_size": 732,  # s1v3.ckpt 모델에 맞춤
            "embedding_dim": 512,
            "hidden_dim": 512,
            "head": 16,
            "linear_units": 2048,
            "n_layer": 24,
            "dropout": 0,
            "EOS": 1024,
        },
        "optimizer": {
            "lr": 0.01,
            "lr_init": 0.00001,
            "lr_end": 0.0001,
            "warmup_steps": 2000,
            "decay_steps": 40000,
        },
        "output_dir": str((opt_dir / f"logs_s1_{version}").absolute()),
        "pretrained_s1": str(pretrained["gpt"].absolute()),
        "version": version,
        # 필수 경로 추가 (데이터셋 준비 결과)
        "train_semantic_path": str((opt_dir / "6-name2semantic.tsv").absolute()),
        "train_phoneme_path": str((opt_dir / "2-name2text.txt").absolute()),
    }

    config_path = opt_dir / "s1_config.yaml"

    # YAML 출력
    try:
        import yaml
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(s1_config, f, allow_unicode=True, default_flow_style=False)
    except ImportError:
        # YAML 없으면 JSON으로 대체 (s1_train.py가 지원하는 경우)
        config_path = opt_dir / "s1_config.json"
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(s1_config, f, ensure_ascii=False, indent=2)

    emit_progress("gpt_training", 0.60, f"GPT 학습 시작 (에포크: {epochs})")

    env = os.environ.copy()
    # PYTHONPATH 설정 (GPT_SoVITS 모듈 + 루트의 tools/utils 모듈)
    gpt_sovits_dir = str(gpt_sovits_path / "GPT_SoVITS")
    root_dir = str(gpt_sovits_path)

    # hz 환경변수 추가 (시맨틱 프레임레이트)
    env["hz"] = "25hz"

    # sys.path 설정 후 runpy로 스크립트 실행 (multiprocessing 호환)
    # 절대 경로로 변환 (cwd가 다른 디렉토리로 설정되므로)
    abs_config_path = config_path.absolute()
    abs_train_script = train_script.absolute()
    wrapper_code = f"""
import sys
sys.path.insert(0, r'{gpt_sovits_dir}')
sys.path.insert(0, r'{root_dir}')
sys.argv = ['s1_train.py', '-c', r'{abs_config_path}']
import runpy
runpy.run_path(r'{abs_train_script}', run_name='__main__')
"""

    try:
        process = subprocess.Popen(
            [str(python_exe), "-c", wrapper_code],
            cwd=str(gpt_sovits_path / "GPT_SoVITS"),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )

        current_epoch = 0
        last_lines = []  # 마지막 출력 라인들 (에러 진단용)
        max_lines = 20
        line_count = 0
        last_step_progress = -1  # 스텝 진행률 추적 (10% 단위)
        import time as time_module

        for line in iter(process.stdout.readline, ""):
            line = line.strip()
            if not line:
                continue

            line_count += 1

            # 에러 진단용 마지막 라인 저장
            last_lines.append(line)
            if len(last_lines) > max_lines:
                last_lines.pop(0)

            # 에포크 진행 파싱 (다양한 형식 지원)
            epoch_parsed = False
            step_parsed = False

            if "Epoch" in line:
                try:
                    import re
                    # "Epoch X/Y" 형식
                    match = re.search(r"Epoch\s*(\d+)\s*/\s*(\d+)", line)
                    if match:
                        current_epoch = int(match.group(1))
                        total = int(match.group(2))
                        epoch_parsed = True
                    else:
                        # "Epoch X:" 형식 (PyTorch Lightning)
                        match = re.search(r"Epoch\s*(\d+)\s*:", line)
                        if match:
                            current_epoch = int(match.group(1)) + 1  # 0-indexed → 1-indexed
                            total = epochs  # 함수 파라미터 사용
                            epoch_parsed = True

                    if epoch_parsed:
                        progress = 0.60 + (current_epoch / total) * 0.35
                        emit_progress("gpt_training", progress,
                                      f"GPT 학습 중: 에포크 {current_epoch}/{total}",
                                      current_epoch=current_epoch, total_epochs=total)
                        logger.info(f"[GPT] 에포크 {current_epoch}/{total}")
                except Exception as e:
                    logger.warning(f"[GPT] 에포크 파싱 실패: {e}")

            # Step 파싱 (에포크 없이 스텝만 출력하는 경우)
            elif "step" in line.lower() or "steps" in line.lower():
                try:
                    import re
                    match = re.search(r"(\d+)\s*/\s*(\d+)\s*(?:step|steps)", line.lower())
                    if match:
                        current_step = int(match.group(1))
                        total_steps = int(match.group(2))
                        step_parsed = True
                        # 스텝 기반 진행률 (60% ~ 95%)
                        step_progress = current_step / total_steps if total_steps > 0 else 0
                        progress = 0.60 + step_progress * 0.35
                        # 10% 단위로만 업데이트 (과다 로그 방지)
                        current_step_progress = int(step_progress * 10)
                        if current_step_progress != last_step_progress:
                            last_step_progress = current_step_progress
                            emit_progress("gpt_training", progress,
                                          f"GPT 학습 중: 스텝 {current_step}/{total_steps}")
                except Exception:
                    pass

            # 50줄마다 heartbeat 진행 업데이트 (학습 중임을 알림)
            if line_count % 50 == 0 and not epoch_parsed and not step_parsed:
                base_progress = 0.60 + (current_epoch / epochs) * 0.35 if current_epoch > 0 else 0.61
                emit_progress("gpt_training", base_progress,
                              f"GPT 학습 진행 중... (라인 {line_count})")

            # 중요 로그만 출력 (과다 로그 방지)
            is_important = (
                epoch_parsed or
                "error" in line.lower() or
                "warning" in line.lower() or
                "saved" in line.lower() or
                "checkpoint" in line.lower() or
                line.startswith("INFO:__main__:")
            )
            if is_important:
                logger.info(f"[GPT] {line}")
            elif line_count <= 10 or line_count % 100 == 0:
                # 처음 10줄과 100줄마다만 출력
                logger.debug(f"[GPT] {line}")

        process.wait()
        if process.returncode != 0:
            error_detail = "\n".join(last_lines[-10:]) if last_lines else "출력 없음"
            emit_error("GPT 학습 실패", f"exit code: {process.returncode}\n{error_detail}")
            return False

    except Exception as e:
        emit_error("GPT 학습 오류", str(e))
        return False

    return True


def setup_reference_audios(sliced_dir: Path, list_path: Path, output_dir: Path,
                          char_name: str, max_refs: int = 10):
    """참조 오디오 정보를 info.json에 저장 (파일 복사 없이 preprocessed 폴더 참조)

    Args:
        sliced_dir: 슬라이싱된 오디오 디렉토리 (preprocessed 폴더)
        list_path: 학습 리스트 파일 경로
        output_dir: 출력 디렉토리 (모델 저장 위치)
        char_name: 캐릭터 이름
        max_refs: 최대 참조 오디오 수
    """
    import wave

    output_dir.mkdir(parents=True, exist_ok=True)

    # 학습 리스트 파싱 (wav_path|speaker|language|text)
    if not list_path.exists():
        logger.warning("학습 리스트 파일이 없습니다")
        return

    ref_audios = []
    with open(list_path, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split("|")
            if len(parts) >= 4:
                wav_path = Path(parts[0])
                text = parts[3]

                if not wav_path.exists():
                    continue

                # 기본 점수
                score = 50

                # 길이 가져오기
                try:
                    with wave.open(str(wav_path), "rb") as wav_file:
                        duration = wav_file.getnframes() / float(wav_file.getframerate())
                except Exception:
                    duration = 5.0

                # 3~10초 범위 선호
                if 3.0 <= duration <= 10.0:
                    score += 20
                elif duration < 3.0:
                    score -= 30
                elif duration > 15.0:
                    score -= 20

                # 텍스트 길이 보너스
                text_len = len(text) if text else 0
                score += min(text_len, 40) // 2

                ref_audios.append({
                    "wav_path": wav_path,
                    "text": text,
                    "score": score,
                    "duration": duration,
                    "text_len": text_len,
                })

    if not ref_audios:
        logger.warning("참조 오디오 후보가 없습니다")
        return

    # 점수 순으로 정렬
    ref_audios.sort(key=lambda x: x["score"], reverse=True)

    # 상위 max_refs개 선택
    selected = ref_audios[:max_refs]

    # info.json 생성 (파일 복사 없이 preprocessed 폴더 직접 참조)
    info_refs = []
    for ref in selected:
        wav_path = ref["wav_path"]
        # preprocessed 폴더 기준 상대 경로
        rel_path = f"preprocessed/{wav_path.name}"
        info_refs.append({
            "audio": rel_path,
            "text": ref["text"],
            "score": ref["score"],
            "text_len": ref["text_len"],
        })
        logger.debug(f"참조 오디오 등록: {rel_path} (score: {ref['score']})")

    # info.json 저장
    if info_refs:
        info = {
            "char_name": char_name,
            "ref_audios": info_refs,
            "mode": "finetuned",
        }
        info_path = output_dir / "info.json"
        with open(info_path, "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=2)
        logger.info(f"참조 오디오 설정 완료: {len(info_refs)}개 (preprocessed 폴더 참조)")


def copy_trained_models(opt_dir: Path, output_dir: Path, exp_name: str, version: str = "v2Pro"):
    """학습된 모델을 출력 디렉토리로 복사"""
    output_dir.mkdir(parents=True, exist_ok=True)

    # SoVITS 모델 복사 (버전별 디렉토리 지원)
    sovits_sources = [
        opt_dir / f"SoVITS_weights_{version}",
        opt_dir / f"logs_s2_{version}",
    ]
    sovits_files = []
    for src in sovits_sources:
        if src.exists():
            sovits_files.extend(src.glob("*.pth"))

    if sovits_files:
        # 가장 최신 파일 선택
        sovits_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        sovits_dst = output_dir / "sovits.pth"
        shutil.copy2(sovits_files[0], sovits_dst)
        logger.info(f"SoVITS 모델 복사: {sovits_files[0]} -> {sovits_dst}")
    else:
        logger.warning("SoVITS 모델 파일을 찾을 수 없습니다")

    # GPT 모델 복사 (버전별 디렉토리 지원)
    gpt_sources = [
        opt_dir / f"GPT_weights_{version}",
        opt_dir / f"logs_s1_{version}",
        opt_dir / "GPT_weights",
    ]
    gpt_files = []
    for src in gpt_sources:
        if src.exists():
            gpt_files.extend(src.glob("*.ckpt"))

    if gpt_files:
        gpt_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        gpt_dst = output_dir / "gpt.ckpt"
        shutil.copy2(gpt_files[0], gpt_dst)
        logger.info(f"GPT 모델 복사: {gpt_files[0]} -> {gpt_dst}")
    else:
        logger.warning("GPT 모델 파일을 찾을 수 없습니다")


def finetune_character(
    char_id: str,
    char_name: str,
    audio_dir: Path,
    output_dir: Path,
    gamedata_path: Path,
    gpt_sovits_path: Path,
    language: str = "ko",
    epochs_sovits: int = 8,
    epochs_gpt: int = 15,
    version: str = "v2Pro",
    cleanup: bool = True,
):
    """캐릭터 음성 모델 Fine-tuning 메인 함수

    Args:
        char_id: 캐릭터 ID (예: char_002_amiya)
        char_name: 캐릭터 이름 (예: 아미야)
        audio_dir: 원본 오디오 디렉토리
        output_dir: 출력 디렉토리 (모델 저장 위치)
        gamedata_path: 게임 데이터 경로 (charword_table.json 위치)
        gpt_sovits_path: GPT-SoVITS 설치 경로
        language: 언어 코드 (ko, ja, zh, en)
        epochs_sovits: SoVITS 학습 에포크 수
        epochs_gpt: GPT 학습 에포크 수
        version: 모델 버전 (v2Pro 권장)
    """
    emit_progress("starting", 0.0, f"학습 시작: {char_name} ({version})")

    # 전처리된 파일 확인 (음성 준비 단계에서 생성됨)
    from core.voice.gpt_sovits.config import GPTSoVITSConfig
    from core.voice.gpt_sovits.audio_preprocessor import AudioSegment
    config = GPTSoVITSConfig()

    preprocessed_dir = config.get_preprocessed_audio_path(char_id)

    if not preprocessed_dir.exists():
        emit_error(
            "전처리된 음성 파일이 없습니다",
            "먼저 '음성 준비'를 실행하여 오디오를 전처리해주세요."
        )
        return False

    # 1. 전처리된 세그먼트 로드 (preprocessed 폴더의 WAV + TXT 파일 쌍)
    emit_progress("loading", 0.05, "전처리된 세그먼트 로드 중")
    try:
        segments = []
        wav_files = sorted(preprocessed_dir.glob("*.wav"))

        if not wav_files:
            emit_error(
                "전처리된 음성 파일이 없습니다",
                "먼저 '음성 준비'를 실행하여 오디오를 전처리해주세요."
            )
            return False

        for wav_path in wav_files:
            txt_path = wav_path.with_suffix(".txt")
            if not txt_path.exists():
                logger.warning(f"텍스트 파일 없음: {txt_path}")
                continue

            text = txt_path.read_text(encoding="utf-8").strip()
            if not text:
                logger.warning(f"빈 텍스트 파일: {txt_path}")
                continue

            # voice_id와 segment_index 추출 (파일명: CN_001_00.wav → voice_id=CN_001, index=0)
            stem = wav_path.stem
            if "_" in stem:
                parts = stem.rsplit("_", 1)
                if parts[-1].isdigit():
                    voice_id = parts[0]
                    seg_index = int(parts[-1])
                else:
                    voice_id = stem
                    seg_index = 0
            else:
                voice_id = stem
                seg_index = 0

            # 오디오 길이 계산
            try:
                import wave
                with wave.open(str(wav_path), "rb") as wav_file:
                    duration = wav_file.getnframes() / float(wav_file.getframerate())
            except Exception:
                duration = 5.0  # 기본값

            segments.append(AudioSegment(
                audio_path=wav_path,
                text=text,
                duration=duration,
                original_voice_id=voice_id,
                segment_index=seg_index,
            ))

        if not segments:
            emit_error("전처리된 세그먼트 로드 실패", "유효한 세그먼트가 없습니다")
            return False

        emit_progress("loading", 0.08, f"{len(segments)}개 전처리된 세그먼트 로드 완료")

    except Exception as e:
        emit_error("전처리 데이터 로드 실패", str(e))
        return False

    # 2. 학습 리스트 생성 (전처리된 세그먼트 사용)
    emit_progress("transcribing", 0.10, "학습 리스트 생성 중")
    training_data_dir = output_dir / "training_data"
    training_data_dir.mkdir(parents=True, exist_ok=True)
    list_path = training_data_dir / "train.list"

    item_count = create_training_list_v2(segments, list_path, char_name, language)

    if item_count == 0:
        emit_error("학습 리스트 생성 실패", "유효한 세그먼트가 없습니다")
        return False

    emit_progress("transcribing", 0.15, f"학습 리스트 생성 완료: {item_count}개 항목")

    # sliced_dir은 전처리된 디렉토리 사용
    sliced_dir = preprocessed_dir

    # 4. 데이터셋 준비
    emit_progress("preparing", 0.20, "데이터셋 준비 중")
    opt_dir = training_data_dir / "dataset"
    if not run_dataset_preparation(gpt_sovits_path, list_path, char_id, opt_dir, sliced_dir, version):
        # run_dataset_preparation에서 이미 에러를 emit함
        return False

    # 4.1 데이터셋 준비 결과 검증
    valid, msg = verify_dataset_preparation(opt_dir, version, language)
    if not valid:
        emit_error("데이터셋 준비 실패", msg)
        return False

    # 5. SoVITS 학습
    emit_progress("sovits_training", 0.40, "SoVITS 학습 중")
    if not run_sovits_training(gpt_sovits_path, char_id, opt_dir, epochs_sovits,
                               version=version):
        # run_sovits_training에서 이미 상세 에러를 emit함
        return False

    # 6. GPT 학습
    emit_progress("gpt_training", 0.60, "GPT 학습 중")
    if not run_gpt_training(gpt_sovits_path, char_id, opt_dir, epochs_gpt,
                            version=version):
        # run_gpt_training에서 이미 상세 에러를 emit함
        return False

    # 7. 모델 복사
    emit_progress("finalizing", 0.95, "모델 복사 중")
    copy_trained_models(opt_dir, output_dir, char_id, version)

    # 8. 참조 오디오 설정
    setup_reference_audios(sliced_dir, list_path, output_dir, char_name)

    # 9. 학습 중간 산출물 정리 (cleanup 옵션이 활성화된 경우)
    cleaned_size = 0
    if cleanup:
        emit_progress("cleanup", 0.98, "학습 중간 산출물 정리 중...")
        cleaned_size = cleanup_training_data(output_dir)
        if cleaned_size > 0:
            size_gb = cleaned_size / (1024 ** 3)
            emit_progress("cleanup", 0.99, f"정리 완료: {size_gb:.2f}GB 확보")

    emit_complete(char_id, char_name, cleaned_size)
    return True


def main():
    parser = argparse.ArgumentParser(description="GPT-SoVITS Fine-tuning 워커")
    parser.add_argument("--char-id", required=True, help="캐릭터 ID")
    parser.add_argument("--char-name", required=True, help="캐릭터 이름")
    parser.add_argument("--audio-dir", required=True, help="오디오 디렉토리")
    parser.add_argument("--output-dir", required=True, help="출력 디렉토리")
    parser.add_argument("--gamedata-path", required=True, help="게임 데이터 경로")
    parser.add_argument("--gpt-sovits-path", required=True, help="GPT-SoVITS 경로")
    parser.add_argument("--language", default="ko", help="언어 코드")
    parser.add_argument("--epochs-sovits", type=int, default=8, help="SoVITS 에포크")
    parser.add_argument("--epochs-gpt", type=int, default=15, help="GPT 에포크")
    parser.add_argument("--version", default="v2Pro", help="모델 버전 (v2Pro 권장)")
    parser.add_argument("--cleanup", action="store_true", default=True,
                        help="학습 완료 후 중간 산출물 정리 (기본값: True)")
    parser.add_argument("--no-cleanup", dest="cleanup", action="store_false",
                        help="학습 완료 후 중간 산출물 유지")

    args = parser.parse_args()

    success = finetune_character(
        char_id=args.char_id,
        char_name=args.char_name,
        audio_dir=Path(args.audio_dir),
        output_dir=Path(args.output_dir),
        gamedata_path=Path(args.gamedata_path),
        gpt_sovits_path=Path(args.gpt_sovits_path),
        language=args.language,
        epochs_sovits=args.epochs_sovits,
        epochs_gpt=args.epochs_gpt,
        version=args.version,
        cleanup=args.cleanup,
    )

    if success:
        # CTranslate2 모델 소멸자 크래시 방지 (training_worker.py 참조)
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
