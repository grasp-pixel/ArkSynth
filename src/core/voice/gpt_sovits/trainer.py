"""GPT-SoVITS 음성 준비/학습 로직

GPT-SoVITS를 사용한 캐릭터 음성 클로닝.
- prepare 모드: Zero-shot용 참조 오디오만 준비 (빠름)
- finetune 모드: 실제 모델 학습 (느리지만 고품질)
"""

import asyncio
import json
import logging
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from .config import GPTSoVITSConfig
from .model_manager import GPTSoVITSModelManager

logger = logging.getLogger(__name__)


@dataclass
class TrainingProgress:
    """음성 준비 진행 상황"""

    stage: str  # preprocessing, complete
    progress: float  # 0.0 ~ 1.0
    current_epoch: int = 0  # 미사용 (zero-shot 모드)
    total_epochs: int = 0   # 미사용 (zero-shot 모드)
    message: str = ""


class GPTSoVITSTrainer:
    """GPT-SoVITS 음성 준비/학습기

    prepare 모드: 참조 오디오와 텍스트만 준비 (Zero-shot 합성용)
    finetune 모드: 실제 GPT-SoVITS 모델 학습 (고품질)

    subprocess로 worker 스크립트를 실행하여 비동기 처리.
    """

    def __init__(
        self,
        config: Optional[GPTSoVITSConfig] = None,
        model_manager: Optional[GPTSoVITSModelManager] = None,
    ):
        self.config = config or GPTSoVITSConfig()
        self.model_manager = model_manager or GPTSoVITSModelManager(self.config)
        self._cancelled = False
        self._process: Optional[subprocess.Popen] = None
        self._last_error: str = ""

    @property
    def last_error(self) -> str:
        """마지막 에러 메시지"""
        return self._last_error

    def cancel(self):
        """학습 취소"""
        self._cancelled = True
        if self._process and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()

    async def train(
        self,
        char_id: str,
        char_name: str,
        audio_files: list[Path],
        mode: str = "prepare",
        on_progress: Optional[Callable[[TrainingProgress], None]] = None,
    ) -> bool:
        """캐릭터 음성 모델 준비/학습

        Args:
            char_id: 캐릭터 ID
            char_name: 캐릭터 이름
            audio_files: 학습용 오디오 파일 목록 (사용하지 않음, audio_dir에서 자동 탐색)
            mode: "prepare" (Zero-shot 준비) 또는 "finetune" (실제 학습)
            on_progress: 진행 상황 콜백

        Returns:
            bool: 학습 성공 여부
        """
        self._cancelled = False
        self._last_error = ""

        # 디버그: CWD 로깅
        import os
        logger.info(f"[Debug] CWD: {os.getcwd()}")
        logger.info(f"[Debug] audio_files: {len(audio_files) if audio_files else 0}개")

        # 오디오 디렉토리 결정 (extracted/{lang_folder}/{char_id}/ 구조)
        if audio_files:
            audio_dir = audio_files[0].parent.absolute()
            logger.info(f"[Debug] audio_dir from files: {audio_dir}")
        else:
            # 언어별 폴더 매핑
            from ...common.language_codes import SHORT_TO_VOICE_FOLDER
            lang_folder = SHORT_TO_VOICE_FOLDER.get(self.config.default_language, "voice")
            audio_dir = (self.config.extracted_path / lang_folder / char_id).absolute()
            logger.info(f"[Debug] audio_dir from config: {audio_dir}")

            # 폴백: 언어별 폴더가 없으면 기본 voice 폴더 시도
            if not audio_dir.exists():
                logger.warning(f"언어별 폴더 없음: {audio_dir}, 기본 폴더 시도")
                audio_dir = (self.config.extracted_path / "voice" / char_id).absolute()

        if not audio_dir.exists():
            logger.error(f"오디오 디렉토리가 없습니다: {audio_dir}")
            self._last_error = f"오디오 디렉토리가 없습니다: {audio_dir}"
            return False

        output_dir = self.config.get_model_path(char_id)  # default_language 사용
        output_dir.mkdir(parents=True, exist_ok=True)

        # mode에 따라 워커 스크립트 선택
        if mode == "finetune":
            worker_script = Path(__file__).parent / "finetuning_worker.py"
        else:
            worker_script = Path(__file__).parent / "training_worker.py"

        # gamedata 경로 (charword_table.json 위치)
        from ...backend.config import config as server_config
        gamedata_path = server_config.gamedata_path

        # 모든 경로를 절대 경로로 변환 (subprocess CWD와 무관하게 동작하도록)
        cmd = [
            sys.executable,
            str(worker_script.absolute()),
            "--char-id", char_id,
            "--char-name", char_name,
            "--audio-dir", str(audio_dir.absolute()),
            "--output-dir", str(output_dir.absolute()),
            "--gamedata-path", str(gamedata_path.absolute()),
            "--gpt-sovits-path", str(self.config.gpt_sovits_path.absolute()),
            "--epochs-sovits", str(self.config.epochs_sovits),
            "--epochs-gpt", str(self.config.epochs_gpt),
            "--language", self.config.default_language,
        ]

        # finetune 모드: cleanup 옵션 전달
        if mode == "finetune":
            if self.config.cleanup_after_training:
                cmd.append("--cleanup")
            else:
                cmd.append("--no-cleanup")

        mode_label = "학습" if mode == "finetune" else "준비"
        logger.info(f"{mode_label} 시작: {char_id} ({char_name}) [mode={mode}]")
        logger.debug(f"명령: {' '.join(cmd)}")

        try:
            logger.info(f"워커 실행: {' '.join(cmd[:3])}...")  # 명령어 일부만 로깅
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # stderr를 stdout으로 리다이렉트
                text=True,
                encoding="utf-8",
                errors="replace",  # 디코딩 실패 시 대체 문자 사용
                bufsize=1,  # 라인 버퍼링
            )

            # stdout에서 진행 상황 읽기 (stderr 포함)
            success = await self._read_progress(on_progress)

            if success:
                # 모델 정보 저장
                if mode == "finetune":
                    # Fine-tuned: 실제 에포크 수 저장
                    epochs_sovits = self.config.epochs_sovits
                    epochs_gpt = self.config.epochs_gpt
                else:
                    # Zero-shot 준비: epochs=0
                    epochs_sovits = 0
                    epochs_gpt = 0

                self.model_manager.create_model_info(
                    char_id=char_id,
                    char_name=char_name,
                    epochs_sovits=epochs_sovits,
                    epochs_gpt=epochs_gpt,
                    ref_audio_count=len(list(audio_dir.glob("*.mp3"))) + len(list(audio_dir.glob("*.wav"))),
                    language=self.config.default_language,
                )
                logger.info(f"음성 {mode_label} 완료: {char_id} ({char_name})")
            else:
                logger.error(f"음성 준비 실패: {char_id}")

            return success

        except Exception as e:
            logger.error(f"학습 중 오류 ({char_id}): {e}")
            return False

        finally:
            self._process = None

    async def _read_progress(
        self,
        on_progress: Optional[Callable[[TrainingProgress], None]] = None,
    ) -> bool:
        """subprocess stdout에서 진행 상황 읽기"""
        if not self._process or not self._process.stdout:
            return False

        loop = asyncio.get_event_loop()

        while True:
            if self._cancelled:
                return False

            # 비동기로 stdout 읽기
            line = await loop.run_in_executor(None, self._process.stdout.readline)

            if not line:
                # 프로세스 종료
                break

            line = line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)
                msg_type = data.get("type")

                if msg_type == "progress":
                    if on_progress:
                        on_progress(
                            TrainingProgress(
                                stage=data.get("stage", ""),
                                progress=data.get("progress", 0),
                                current_epoch=data.get("current_epoch", 0),
                                total_epochs=data.get("total_epochs", 0),
                                message=data.get("message", ""),
                            )
                        )

                elif msg_type == "error":
                    error_msg = data.get('message', '학습 실패')
                    error_detail = data.get('error', '')
                    self._last_error = f"{error_msg}: {error_detail}" if error_detail else error_msg
                    logger.error(f"워커 에러: {self._last_error}")
                    return False

                elif msg_type == "complete":
                    if on_progress:
                        on_progress(
                            TrainingProgress(
                                stage="complete",
                                progress=1.0,
                                message=f"{data.get('char_name')} 학습 완료!",
                            )
                        )
                    return True

            except json.JSONDecodeError:
                # 에러/트레이스백 감지
                if "error" in line.lower() or "traceback" in line.lower() or "exception" in line.lower():
                    logger.warning(f"워커 출력: {line}")
                    self._last_error = line
                # 에포크, 손실 등 중요 정보는 info 레벨로 출력
                elif "epoch" in line.lower() or "loss" in line.lower() or "step" in line.lower():
                    logger.info(f"워커 출력: {line}")
                else:
                    logger.debug(f"워커 출력: {line}")

        # 프로세스 종료 코드 확인
        return_code = self._process.wait()
        if return_code != 0:
            logger.error(f"워커 프로세스 종료 코드: {return_code}")
            if self._last_error:
                logger.error(f"마지막 에러: {self._last_error}")
        return return_code == 0
