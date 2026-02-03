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


def preprocess_text_for_tts(text: str) -> str:
    """TTS 합성을 위한 텍스트 전처리

    GPT-SoVITS가 제대로 처리하지 못하는 패턴을 변환합니다.
    """
    import re

    # 괄호 안의 감탄사/의성어 제거 (예: "(한숨)" -> "")
    # TTS로 읽을 필요 없는 연출 지시문
    text = re.sub(r'\([^)]+\)', '', text)

    # 연속된 마침표 및 말줄임표 처리 (... 또는 … -> 쉼표)
    # GPT-SoVITS는 ...을 무시하거나 앞 문장을 스킵할 수 있음
    text = re.sub(r'\.{2,}', ', ', text)
    text = re.sub(r'…+', ', ', text)  # 유니코드 말줄임표(…)도 처리

    # 문장 중간의 마침표를 쉼표로 대체 (GPT-SoVITS 문장 분할 방지)
    # 마침표 뒤에 텍스트가 더 있는 경우에만 변환
    # "하이디 씨. 겨우" -> "하이디 씨, 겨우"
    text = re.sub(r'\.\s+(?=\S)', ', ', text)

    # 연속된 물음표/느낌표 단순화
    text = re.sub(r'[?!]{2,}', '?', text)

    # 앞뒤 공백 및 연속 공백 정리
    text = re.sub(r'\s+', ' ', text).strip()

    # 문장 시작의 쉼표/마침표 제거
    text = re.sub(r'^[,.\s]+', '', text)

    # 연속된 쉼표 정리
    text = re.sub(r',\s*,+', ',', text)

    return text


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
        """API 서버 실행 중인지 확인

        GPT-SoVITS API는 루트 엔드포인트가 없을 수 있으므로,
        연결 가능 여부로 판단합니다.
        """
        try:
            session = await self._get_session()
            # GPT-SoVITS v2는 /tts 엔드포인트가 GET으로 접근 시 405를 반환하지만
            # 서버가 실행 중임을 의미함. 연결 자체가 되면 실행 중으로 판단
            async with session.get(
                f"{self.api_url}/",
                timeout=aiohttp.ClientTimeout(total=10)  # 합성 중에도 여유 있게
            ) as resp:
                # 200, 404, 405 등 어떤 응답이든 서버가 살아있음
                return True
        except aiohttp.ClientConnectorError as e:
            # 연결 불가 = 서버 미실행
            logger.warning(f"[API 상태] 연결 불가: {e}")
            return False
        except asyncio.TimeoutError:
            logger.warning(f"[API 상태] 타임아웃 (10초)")
            return False
        except Exception as e:
            logger.warning(f"[API 상태] 예외: {type(e).__name__}: {e}")
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

            if not api_script.exists():
                logger.error(f"API 스크립트를 찾을 수 없습니다: {api_script}")
                return False

            # config에서 Python 경로 가져오기 (자동 설치/통합패키지/venv 순으로 탐색)
            python_exe = self.config.python_path
            if python_exe is None:
                logger.error(f"GPT-SoVITS Python 경로가 None입니다")
                logger.error(f"  gpt_sovits_path: {self.config.gpt_sovits_path}")
                logger.error(f"  runtime/python.exe 존재: {(self.config.gpt_sovits_path / 'runtime' / 'python.exe').exists()}")
                return False

            if not python_exe.exists():
                logger.error(f"GPT-SoVITS Python이 존재하지 않습니다: {python_exe}")
                return False

            # 절대 경로로 변환 (상대 경로 + cwd 조합 시 경로 중복 방지)
            python_exe_abs = python_exe.absolute()
            api_script_abs = api_script.absolute()
            cwd_abs = self.config.gpt_sovits_path.absolute()

            cmd = [
                str(python_exe_abs),
                str(api_script_abs),
                "-a", self.config.api_host,
                "-p", str(self.config.api_port),
            ]

            logger.info(f"GPT-SoVITS API 서버 시작: {' '.join(cmd)}")
            logger.info(f"  작업 디렉토리: {cwd_abs}")

            # 별도 콘솔 창에서 실행 (파이프 버퍼 문제 방지)
            # CREATE_NEW_CONSOLE: 새 콘솔 창에서 실행되어 로그 확인 가능
            self._api_process = subprocess.Popen(
                cmd,
                cwd=str(cwd_abs),
                stdout=None,  # 콘솔로 직접 출력
                stderr=None,
                creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0,
            )

            # 프로세스가 즉시 종료되었는지 확인 (0.5초 대기)
            import time
            time.sleep(0.5)
            exit_code = self._api_process.poll()
            if exit_code is not None:
                # 프로세스가 종료됨 - 별도 콘솔 창에서 에러 확인 필요
                logger.error(f"API 서버가 즉시 종료됨 (exit code: {exit_code})")
                logger.error("별도 콘솔 창에서 에러 메시지를 확인하세요")
                self._api_process = None
                return False

            logger.info(f"API 서버 프로세스 시작됨 (PID: {self._api_process.pid})")
            return True

        except Exception as e:
            logger.exception(f"API 서버 시작 실패: {e}")
            return False

    def get_api_status(self) -> dict:
        """API 서버 상태 정보 조회"""
        status = {
            "gpt_sovits_installed": self.config.is_gpt_sovits_installed,
            "gpt_sovits_path": str(self.config.gpt_sovits_path),
            "python_path": str(self.config.python_path) if self.config.python_path else None,
            "api_url": self.api_url,
            "process_running": False,
            "process_pid": None,
            "api_script_exists": False,
        }

        # API 스크립트 존재 확인
        api_script = self.config.gpt_sovits_path / "api_v2.py"
        if not api_script.exists():
            api_script = self.config.gpt_sovits_path / "api.py"
        status["api_script_exists"] = api_script.exists()
        status["api_script_path"] = str(api_script)

        # 프로세스 상태
        if self._api_process:
            exit_code = self._api_process.poll()
            if exit_code is None:
                status["process_running"] = True
                status["process_pid"] = self._api_process.pid
            else:
                status["process_exit_code"] = exit_code

        return status

    def get_process_output(self, max_lines: int = 50) -> str:
        """프로세스 출력 읽기 (비차단)

        Note: 별도 콘솔 창에서 실행되므로 출력을 직접 읽을 수 없습니다.
        콘솔 창에서 로그를 확인하세요.
        """
        if not self._api_process:
            return "[프로세스 없음]"

        exit_code = self._api_process.poll()
        if exit_code is not None:
            return f"[프로세스 종료됨 (exit code: {exit_code})]"

        return "[별도 콘솔 창에서 로그 확인]"

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

    def _select_reference_audio(self, char_id: str, text: str) -> tuple[Path, str]:
        """텍스트에 적합한 참조 오디오 선택

        텍스트 길이에 따라 비슷한 길이의 참조 오디오를 선택합니다.
        다양한 톤을 위해 텍스트 길이 기반으로 선택합니다.

        Args:
            char_id: 캐릭터 ID
            text: 합성할 텍스트

        Returns:
            (참조 오디오 경로, 참조 텍스트) 튜플
        """
        model_dir = self.config.get_model_path(char_id)
        text_len = len(text)

        # 모든 참조 오디오 수집
        refs = []

        # 기본 참조 (ref.wav)
        ref_audio = model_dir / "ref.wav"
        ref_text_file = model_dir / "ref.txt"
        if ref_audio.exists():
            ref_text = ref_text_file.read_text(encoding="utf-8").strip() if ref_text_file.exists() else ""
            refs.append((ref_audio, ref_text, len(ref_text)))

        # 추가 참조 (ref_1.wav, ref_2.wav, ... 최대 30개)
        for i in range(1, 30):
            ref_audio = model_dir / f"ref_{i}.wav"
            ref_text_file = model_dir / f"ref_{i}.txt"
            if ref_audio.exists():
                ref_text = ref_text_file.read_text(encoding="utf-8").strip() if ref_text_file.exists() else ""
                refs.append((ref_audio, ref_text, len(ref_text)))

        if not refs:
            # 폴백: 기본 경로 반환
            return self.config.get_ref_audio_path(char_id), ""

        # 텍스트 길이에 가장 가까운 참조 선택
        # 짧은 텍스트(<=15자)는 짧은 참조, 긴 텍스트(>30자)는 긴 참조 선호
        best_ref = refs[0]
        best_diff = abs(refs[0][2] - text_len)

        for ref_audio, ref_text, ref_len in refs:
            diff = abs(ref_len - text_len)
            if diff < best_diff:
                best_diff = diff
                best_ref = (ref_audio, ref_text, ref_len)

        return best_ref[0], best_ref[1]

    def _get_audio_duration(self, audio_path: Path) -> float:
        """오디오 파일 길이 반환 (초)"""
        try:
            import wave
            with wave.open(str(audio_path), "rb") as wav:
                frames = wav.getnframes()
                rate = wav.getframerate()
                return frames / float(rate)
        except Exception:
            return 0.0

    def _get_aux_reference_audios(self, char_id: str, primary_ref: Path) -> list[str]:
        """추가 참조 오디오 경로 목록 (GPT-SoVITS v2 aux_ref_audio_paths용)

        필터링 조건:
        - 대사(txt 파일)가 있는 음성만 사용
        - 길이가 min~max 범위 내인 음성만 사용

        Args:
            char_id: 캐릭터 ID
            primary_ref: 기본 참조 오디오 (제외됨)

        Returns:
            추가 참조 오디오 경로 목록
        """
        model_dir = self.config.get_model_path(char_id)
        aux_refs = []
        min_len = self.config.min_ref_audio_length
        max_len = self.config.max_ref_audio_length

        def is_valid_ref(audio_path: Path, text_path: Path) -> bool:
            """참조 오디오 유효성 검사"""
            if not audio_path.exists() or audio_path == primary_ref:
                return False
            # 대사 파일이 있고 내용이 있어야 함
            if not text_path.exists():
                return False
            text = text_path.read_text(encoding="utf-8").strip()
            if not text:
                return False
            # 길이 필터링
            duration = self._get_audio_duration(audio_path)
            if duration < min_len or duration > max_len:
                return False
            return True

        # 기본 참조 (ref.wav)
        ref_audio = model_dir / "ref.wav"
        ref_text = model_dir / "ref.txt"
        if is_valid_ref(ref_audio, ref_text):
            aux_refs.append(str(ref_audio.absolute()))

        # 추가 참조 (ref_1.wav ~ ref_99.wav)
        for i in range(1, 100):
            ref_audio = model_dir / f"ref_{i}.wav"
            ref_text = model_dir / f"ref_{i}.txt"
            if is_valid_ref(ref_audio, ref_text):
                aux_refs.append(str(ref_audio.absolute()))

        return aux_refs

    async def synthesize(
        self,
        text: str,
        char_id: str,
        language: str = "ko",
    ) -> Optional[bytes]:
        """텍스트를 음성으로 합성

        텍스트 길이에 따라 적절한 참조 오디오를 자동 선택합니다.

        Args:
            text: 합성할 텍스트
            char_id: 캐릭터 ID
            language: 텍스트 언어

        Returns:
            WAV 오디오 데이터 또는 None
        """
        # 텍스트 전처리 (GPT-SoVITS 호환성)
        original_text = text
        text = preprocess_text_for_tts(text)
        if text != original_text:
            logger.info(f"[합성] 텍스트 전처리: '{original_text[:30]}...' -> '{text[:30]}...'")

        # 텍스트에 적합한 참조 오디오 선택
        logger.info(f"[합성] 참조 오디오 선택 중...")
        ref_audio_path, ref_text = self._select_reference_audio(char_id, text)

        if not ref_audio_path.exists():
            logger.error(f"참조 오디오가 없습니다: {char_id}")
            return None

        logger.info(f"[합성] 기본 참조: {ref_audio_path.name} (대사: {ref_text[:20]}...)" if ref_text else f"[합성] 기본 참조: {ref_audio_path.name}")

        # 추가 참조 오디오 (대사 있고 길이 적절한 모든 음성)
        aux_refs = self._get_aux_reference_audios(char_id, ref_audio_path)
        if aux_refs:
            logger.info(f"[합성] 추가 참조: {len(aux_refs)}개")

        # prompt_text 처리: 너무 길면 모델이 이어서 말하는 문제 발생
        # 마지막 문장만 사용하여 음성 특성 참조에 충분하면서 bleeding 방지
        prompt_text = ref_text
        if ref_text and len(ref_text) > 40:
            # 마지막 문장 추출 (문장 부호 기준)
            import re
            sentences = re.split(r'[.!?。！？]', ref_text)
            sentences = [s.strip() for s in sentences if s.strip()]
            if sentences:
                prompt_text = sentences[-1]
                # 너무 짧으면 마지막 2문장 사용
                if len(prompt_text) < 10 and len(sentences) >= 2:
                    prompt_text = sentences[-2] + ". " + sentences[-1]
            logger.info(f"[합성] prompt_text 축약: {len(ref_text)}자 -> {len(prompt_text)}자")

        # GPT-SoVITS 분할 기능이 한국어에서 문제가 있어 항상 cut0 사용
        # 긴 텍스트는 우리 코드에서 직접 분할 후 개별 합성
        split_method = "cut0"
        text_len = len(text)

        # GPT-SoVITS v2 언어 코드 변환
        # v2는 "all_ko", "all_ja", "all_zh", "all_en" 등의 형식 사용
        lang_map = {
            "ko": "all_ko",
            "ja": "all_ja",
            "zh": "all_zh",
            "en": "all_en",
        }
        api_lang = lang_map.get(language, language)
        logger.info(f"[합성] 언어: {language} -> {api_lang}")

        params = {
            "text": text,
            "text_lang": api_lang,
            "ref_audio_path": str(ref_audio_path.absolute()),
            "aux_ref_audio_paths": aux_refs,  # 추가 참조 오디오 (품질 향상)
            "prompt_text": prompt_text,  # 참조 오디오의 마지막 문장 (bleeding 방지)
            "prompt_lang": api_lang,
            "top_k": self.config.top_k,
            "top_p": self.config.top_p,
            "temperature": self.config.temperature,
            "text_split_method": split_method,
            "speed_factor": 1.0,
        }

        logger.info(f"[합성] GPT-SoVITS API 요청 전송 중... (텍스트: {text_len}자, 분할: {split_method})")

        import time
        start_time = time.time()

        # 매 요청마다 새 세션 사용 (GPT-SoVITS 서버 호환성)
        # GPT-SoVITS는 단일 스레드로 동작하여 연결 재사용 시 문제 발생 가능
        connector = aiohttp.TCPConnector(force_close=True)
        timeout = aiohttp.ClientTimeout(total=90)  # 첫 합성 시 모델 로드 포함

        try:
            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                async with session.post(
                    f"{self.api_url}/tts",
                    json=params,
                ) as resp:
                    elapsed = time.time() - start_time

                    if resp.status != 200:
                        error_text = await resp.text()
                        logger.error(f"[합성] 실패 ({elapsed:.1f}초): {error_text}")
                        return None

                    audio_data = await resp.read()
                    logger.info(f"[합성] 완료 ({elapsed:.1f}초, {len(audio_data):,} bytes)")

                    # GPT-SoVITS 서버 안정화를 위한 짧은 대기
                    # 단일 스레드 서버라 연속 요청 시 문제 발생 가능
                    await asyncio.sleep(0.5)

                    return audio_data

        except asyncio.TimeoutError:
            logger.error("[합성] 시간 초과 (90초)")
            return None
        except aiohttp.ClientError as e:
            logger.error(f"[합성] HTTP 오류: {type(e).__name__}: {e}")
            return None
        except Exception as e:
            logger.error(f"[합성] 오류: {type(e).__name__}: {e}")
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
