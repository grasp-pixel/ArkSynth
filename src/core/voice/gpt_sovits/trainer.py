"""GPT-SoVITS 음성 준비 로직

GPT-SoVITS를 사용한 캐릭터 음성 클로닝.
Zero-shot 모드: 참조 오디오만 준비하면 사전 학습된 모델로 합성 가능.
(전체 학습 없이도 음성 클로닝 가능)
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
    """GPT-SoVITS 음성 준비기

    Zero-shot 모드: 참조 오디오와 텍스트만 준비합니다.
    사전 학습된 GPT-SoVITS 모델을 사용해 바로 합성 가능.
    subprocess로 training_worker.py를 실행하여 비동기 처리.
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
        on_progress: Optional[Callable[[TrainingProgress], None]] = None,
    ) -> bool:
        """캐릭터 음성 모델 학습

        Args:
            char_id: 캐릭터 ID
            char_name: 캐릭터 이름
            audio_files: 학습용 오디오 파일 목록 (사용하지 않음, audio_dir에서 자동 탐색)
            on_progress: 진행 상황 콜백

        Returns:
            bool: 학습 성공 여부
        """
        self._cancelled = False
        self._last_error = ""

        # 오디오 디렉토리 결정
        if audio_files:
            audio_dir = audio_files[0].parent
        else:
            audio_dir = self.config.extracted_path / char_id

        if not audio_dir.exists():
            logger.error(f"오디오 디렉토리가 없습니다: {audio_dir}")
            return False

        output_dir = self.config.get_model_path(char_id)
        output_dir.mkdir(parents=True, exist_ok=True)

        # training_worker.py 경로
        worker_script = Path(__file__).parent / "training_worker.py"

        # gamedata 경로 (charword_table.json 위치)
        gamedata_path = Path("data/gamedata_yostar")

        cmd = [
            sys.executable,
            str(worker_script),
            "--char-id", char_id,
            "--char-name", char_name,
            "--audio-dir", str(audio_dir),
            "--output-dir", str(output_dir),
            "--gamedata-path", str(gamedata_path),
            "--gpt-sovits-path", str(self.config.gpt_sovits_path),
            "--epochs-sovits", str(self.config.epochs_sovits),
            "--epochs-gpt", str(self.config.epochs_gpt),
            "--language", self.config.default_language,
        ]

        logger.info(f"학습 시작: {char_id} ({char_name})")
        logger.debug(f"명령: {' '.join(cmd)}")

        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",  # 디코딩 실패 시 대체 문자 사용
                bufsize=1,  # 라인 버퍼링
            )

            # stdout에서 진행 상황 읽기
            success = await self._read_progress(on_progress)

            if success:
                # 모델 정보 저장 (zero-shot 모드: epochs=0)
                self.model_manager.create_model_info(
                    char_id=char_id,
                    char_name=char_name,
                    epochs_sovits=0,  # zero-shot 모드
                    epochs_gpt=0,     # zero-shot 모드
                    ref_audio_count=len(list(audio_dir.glob("*.mp3"))) + len(list(audio_dir.glob("*.wav"))),
                    language=self.config.default_language,
                )
                logger.info(f"음성 준비 완료: {char_id} ({char_name})")
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
                logger.debug(f"워커 출력: {line}")

        # 프로세스 종료 코드 확인
        return_code = self._process.wait()
        return return_code == 0
