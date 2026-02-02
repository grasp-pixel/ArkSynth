"""GPT-SoVITS API 클라이언트

GPT-SoVITS API 서버와 통신하여 음성 합성을 수행합니다.
"""

import asyncio
import logging
import subprocess
import sys
from pathlib import Path
from typing import Optional

import aiohttp

from .config import GPTSoVITSConfig

logger = logging.getLogger(__name__)


class GPTSoVITSAPIClient:
    """GPT-SoVITS API 클라이언트

    GPT-SoVITS API 서버를 관리하고 음성 합성을 수행합니다.
    """

    def __init__(self, config: Optional[GPTSoVITSConfig] = None):
        self.config = config or GPTSoVITSConfig()
        self._api_process: Optional[subprocess.Popen] = None
        self._session: Optional[aiohttp.ClientSession] = None

    @property
    def api_url(self) -> str:
        return self.config.api_url

    async def _get_session(self) -> aiohttp.ClientSession:
        """HTTP 세션 가져오기"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        """리소스 정리"""
        if self._session and not self._session.closed:
            await self._session.close()
        self.stop_api_server()

    async def is_api_running(self) -> bool:
        """API 서버 실행 중인지 확인"""
        try:
            session = await self._get_session()
            async with session.get(f"{self.api_url}/", timeout=aiohttp.ClientTimeout(total=2)) as resp:
                return resp.status == 200
        except Exception:
            return False

    def start_api_server(self) -> bool:
        """GPT-SoVITS API 서버 시작

        Returns:
            bool: 시작 성공 여부
        """
        if not self.config.is_gpt_sovits_installed:
            logger.error(f"GPT-SoVITS가 설치되어 있지 않습니다: {self.config.gpt_sovits_path}")
            return False

        if self._api_process and self._api_process.poll() is None:
            logger.info("API 서버가 이미 실행 중입니다")
            return True

        try:
            # api_v2.py 사용 (참조 오디오 기반 합성 지원)
            api_script = self.config.gpt_sovits_path / "api_v2.py"
            if not api_script.exists():
                api_script = self.config.gpt_sovits_path / "api.py"

            # 통합 패키지는 runtime/python.exe 사용
            python_exe = self.config.gpt_sovits_path / "runtime" / "python.exe"
            if not python_exe.exists():
                # .venv 방식 (소스에서 설치한 경우)
                python_exe = self.config.gpt_sovits_path / ".venv" / "Scripts" / "python.exe"
            if not python_exe.exists():
                logger.error(f"GPT-SoVITS Python을 찾을 수 없습니다: {self.config.gpt_sovits_path}")
                return False

            cmd = [
                str(python_exe),
                str(api_script),
                "-a", self.config.api_host,
                "-p", str(self.config.api_port),
            ]

            logger.info(f"GPT-SoVITS API 서버 시작: {' '.join(cmd)}")

            self._api_process = subprocess.Popen(
                cmd,
                cwd=str(self.config.gpt_sovits_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )

            return True

        except Exception as e:
            logger.error(f"API 서버 시작 실패: {e}")
            return False

    def stop_api_server(self):
        """API 서버 종료"""
        if self._api_process and self._api_process.poll() is None:
            self._api_process.terminate()
            try:
                self._api_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._api_process.kill()
            logger.info("GPT-SoVITS API 서버 종료")
        self._api_process = None

    async def wait_for_api_ready(self, timeout: float = 60.0) -> bool:
        """API 서버가 준비될 때까지 대기

        Args:
            timeout: 최대 대기 시간 (초)

        Returns:
            bool: API 준비 완료 여부
        """
        start_time = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start_time < timeout:
            if await self.is_api_running():
                logger.info("GPT-SoVITS API 서버 준비 완료")
                return True
            await asyncio.sleep(1.0)

        logger.error(f"API 서버 준비 시간 초과 ({timeout}초)")
        return False

    async def set_model(self, char_id: str) -> bool:
        """캐릭터 모델 로드

        Args:
            char_id: 캐릭터 ID

        Returns:
            bool: 모델 로드 성공 여부
        """
        sovits_path = self.config.get_sovits_model_path(char_id)
        gpt_path = self.config.get_gpt_model_path(char_id)

        if not sovits_path.exists() or not gpt_path.exists():
            logger.error(f"모델 파일이 없습니다: {char_id}")
            return False

        try:
            session = await self._get_session()

            # SoVITS 모델 로드
            async with session.get(
                f"{self.api_url}/set_sovits_weights",
                params={"weights_path": str(sovits_path.absolute())},
            ) as resp:
                if resp.status != 200:
                    logger.error(f"SoVITS 모델 로드 실패: {await resp.text()}")
                    return False

            # GPT 모델 로드
            async with session.get(
                f"{self.api_url}/set_gpt_weights",
                params={"weights_path": str(gpt_path.absolute())},
            ) as resp:
                if resp.status != 200:
                    logger.error(f"GPT 모델 로드 실패: {await resp.text()}")
                    return False

            logger.info(f"모델 로드 완료: {char_id}")
            return True

        except Exception as e:
            logger.error(f"모델 로드 중 오류: {e}")
            return False

    async def synthesize(
        self,
        text: str,
        char_id: str,
        language: str = "ko",
    ) -> Optional[bytes]:
        """텍스트를 음성으로 합성

        Args:
            text: 합성할 텍스트
            char_id: 캐릭터 ID
            language: 텍스트 언어

        Returns:
            WAV 오디오 데이터 또는 None
        """
        ref_audio_path = self.config.get_ref_audio_path(char_id)
        ref_text_path = self.config.get_ref_text_path(char_id)

        if not ref_audio_path.exists():
            logger.error(f"참조 오디오가 없습니다: {char_id}")
            return None

        # 참조 텍스트 로드
        ref_text = ""
        if ref_text_path.exists():
            ref_text = ref_text_path.read_text(encoding="utf-8").strip()

        try:
            session = await self._get_session()

            params = {
                "text": text,
                "text_lang": language,
                "ref_audio_path": str(ref_audio_path.absolute()),
                "prompt_text": ref_text,
                "prompt_lang": language,
                "top_k": self.config.top_k,
                "top_p": self.config.top_p,
                "temperature": self.config.temperature,
                "text_split_method": "cut5",  # 문장 단위 분할
                "speed_factor": 1.0,
            }

            async with session.post(
                f"{self.api_url}/tts",
                json=params,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error(f"음성 합성 실패: {error_text}")
                    return None

                audio_data = await resp.read()
                logger.debug(f"음성 합성 완료: {len(audio_data)} bytes")
                return audio_data

        except asyncio.TimeoutError:
            logger.error("음성 합성 시간 초과")
            return None
        except Exception as e:
            logger.error(f"음성 합성 중 오류: {e}")
            return None

    async def synthesize_to_file(
        self,
        text: str,
        char_id: str,
        output_path: Path,
        language: str = "ko",
    ) -> bool:
        """텍스트를 음성으로 합성하여 파일로 저장

        Args:
            text: 합성할 텍스트
            char_id: 캐릭터 ID
            output_path: 출력 파일 경로
            language: 텍스트 언어

        Returns:
            bool: 성공 여부
        """
        audio_data = await self.synthesize(text, char_id, language)
        if audio_data is None:
            return False

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(audio_data)
        return True
