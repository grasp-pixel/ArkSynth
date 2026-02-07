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

# 공통 모듈에서 import
from ..common.text_processor import preprocess_text_for_tts, split_text_for_tts, split_text_with_pauses
from ..common.audio_utils import add_silence_padding, concatenate_wav
from ..common.reference_manager import (
    select_reference_by_score,
    select_reference_hybrid,
    get_all_references_by_score,
    get_audio_duration,
)

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
                timeout=aiohttp.ClientTimeout(total=10),  # 합성 중에도 여유 있게
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
            logger.error(
                f"GPT-SoVITS가 설치되어 있지 않습니다: {self.config.gpt_sovits_path}"
            )
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
                logger.error(
                    f"  runtime/python.exe 존재: {(self.config.gpt_sovits_path / 'runtime' / 'python.exe').exists()}"
                )
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
                "-a",
                self.config.api_host,
                "-p",
                str(self.config.api_port),
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
                creationflags=subprocess.CREATE_NEW_CONSOLE
                if sys.platform == "win32"
                else 0,
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
            "python_path": str(self.config.python_path)
            if self.config.python_path
            else None,
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

    def _select_reference_audio(
        self, char_id: str, input_text_len: int
    ) -> tuple[Path, str]:
        """하이브리드 방식으로 최적의 참조 오디오 선택

        1. 점수 상위 후보 필터링 (품질 보장)
        2. 입력 텍스트 길이 유사도 가중치 적용
        3. 가중 랜덤 선택 (다양성 확보)

        Args:
            char_id: 캐릭터 ID
            input_text_len: 텍스트 길이 기준 (분할 시 평균 세그먼트 길이)

        Returns:
            (참조 오디오 경로, 참조 텍스트) 튜플
        """
        model_dir = self.config.get_model_path(char_id)

        # 하이브리드 선택 (점수 + 텍스트 길이 + 랜덤)
        ref_audio, ref_text, score = select_reference_hybrid(
            model_dir,
            input_text_len=input_text_len,
            min_duration=self.config.min_ref_audio_length,
            max_duration=self.config.max_ref_audio_length,
            top_n=4,
        )

        if ref_audio:
            logger.debug(f"참조 오디오 선택: {ref_audio.name} (score: {score}, text_len: {len(ref_text)})")
            return ref_audio, ref_text

        # 폴백: 기본 경로 반환
        return self.config.get_ref_audio_path(char_id), ""

    def _get_aux_reference_audios(self, char_id: str, primary_ref: Path) -> list[str]:
        """추가 참조 오디오 경로 목록 (GPT-SoVITS v2 aux_ref_audio_paths용)

        점수 순으로 정렬된 참조 오디오 목록을 반환합니다.
        (training_worker와 동일한 로직 사용)

        Args:
            char_id: 캐릭터 ID
            primary_ref: 기본 참조 오디오 (제외됨)

        Returns:
            추가 참조 오디오 경로 목록 (점수 내림차순)
        """
        model_dir = self.config.get_model_path(char_id)

        # 공통 함수로 점수 기반 참조 오디오 목록 조회
        refs = get_all_references_by_score(
            model_dir,
            exclude_primary=primary_ref,
            min_duration=self.config.min_ref_audio_length,
            max_duration=self.config.max_ref_audio_length,
        )

        # 절대 경로 문자열로 변환
        return [str(ref_audio.absolute()) for ref_audio, _, _ in refs]

    async def synthesize(
        self,
        text: str,
        char_id: str,
        language: str = "ko",
        speed_factor: float = 1.0,
        top_k: int = 12,  # 안정성 (5~15 권장)
        top_p: float = 1.0,
        temperature: float = 0.9,  # 약간만 높임 (0.8→0.9)
    ) -> Optional[bytes]:
        """텍스트를 음성으로 합성

        긴 텍스트는 자동으로 분할하여 개별 합성 후 연결합니다.

        Args:
            text: 합성할 텍스트
            char_id: 캐릭터 ID
            language: 텍스트 언어
            speed_factor: 음성 속도 (0.5~2.0)
            top_k: 샘플링 다양성 (1~20)
            top_p: Nucleus sampling (0.1~1.0)
            temperature: 음성 랜덤성 (0.1~2.0)

        Returns:
            WAV 오디오 데이터 또는 None
        """
        # 텍스트 전처리 (GPT-SoVITS 호환성)
        original_text = text
        text = preprocess_text_for_tts(text)

        # 전처리 후 합성 불가능한 텍스트 (말줄임표만 있는 경우 등)
        if text is None:
            logger.info(f"[합성] 스킵 - 합성 불가 텍스트: '{original_text}'")
            return None

        if text != original_text:
            logger.info(
                f"[합성] 텍스트 전처리: '{original_text[:30]}' -> '{text[:30]}'"
            )

        # 텍스트 분할 (구두점 기반 휴지 포함)
        # 쉼표·말줄임표·문장부호에서 분할하고, 각 경계에 적절한 무음 삽입
        segments_with_pauses = split_text_with_pauses(text, max_length=35)

        # 참조 오디오 선택 (분할 후 평균 세그먼트 길이 기준)
        # 실제 합성되는 세그먼트와 참조 텍스트 길이가 비슷해야 품질 좋음
        seg_texts = [s for s, _ in segments_with_pauses]
        avg_segment_len = sum(len(s) for s in seg_texts) // len(seg_texts)
        ref_audio_path, ref_text = self._select_reference_audio(char_id, avg_segment_len)

        if len(segments_with_pauses) == 1:
            # 단일 세그먼트: 직접 합성
            return await self._synthesize_segment(
                segments_with_pauses[0][0],
                char_id,
                language,
                speed_factor=speed_factor,
                top_k=top_k,
                top_p=top_p,
                temperature=temperature,
                ref_audio_path=ref_audio_path,
                ref_text=ref_text,
            )

        # 복수 세그먼트: 분할 합성 후 연결 (세그먼트 간 무음 삽입)
        logger.info(
            f"[합성] 텍스트 분할: {len(text)}자 -> {len(segments_with_pauses)}개 세그먼트 (평균 {avg_segment_len}자)"
        )
        logger.info(f"[합성] 참조: {ref_audio_path.name} (ref_text_len: {len(ref_text)})")
        for i, (seg, pause) in enumerate(segments_with_pauses):
            pause_label = f" +{pause}ms" if pause > 0 else ""
            logger.info(f"  [{i + 1}] {seg[:30]}{'...' if len(seg) > 30 else ''}{pause_label}")

        audio_chunks = []
        for i, (segment, pause) in enumerate(segments_with_pauses):
            logger.info(f"[합성] 세그먼트 {i + 1}/{len(segments_with_pauses)}: {segment[:20]}...")
            chunk = await self._synthesize_segment(
                segment,
                char_id,
                language,
                speed_factor=speed_factor,
                top_k=top_k,
                top_p=top_p,
                temperature=temperature,
                ref_audio_path=ref_audio_path,
                ref_text=ref_text,
                add_padding=(i == 0),  # 첫 세그먼트만 스피커 패딩
            )
            if chunk is None:
                logger.error(f"[합성] 세그먼트 {i + 1} 실패")
                return None
            audio_chunks.append(chunk)

        # WAV 파일 연결 (구두점 기반 무음 삽입)
        pauses = [p for _, p in segments_with_pauses[:-1]]
        return concatenate_wav(audio_chunks, pauses_ms=pauses)

    async def _synthesize_segment(
        self,
        text: str,
        char_id: str,
        language: str = "ko",
        speed_factor: float = 1.0,
        top_k: int = 12,  # 안정성 (5~15 권장)
        top_p: float = 1.0,
        temperature: float = 0.9,  # 약간만 높임 (0.8→0.9)
        ref_audio_path: Path | None = None,
        ref_text: str | None = None,
        add_padding: bool = True,
    ) -> Optional[bytes]:
        """단일 텍스트 세그먼트를 음성으로 합성

        Args:
            text: 합성할 텍스트 (짧은 세그먼트)
            char_id: 캐릭터 ID
            language: 텍스트 언어
            speed_factor: 음성 속도 (0.5~2.0)
            top_k: 샘플링 다양성 (1~20)
            top_p: Nucleus sampling (0.1~1.0)
            temperature: 음성 랜덤성 (0.1~2.0)
            ref_audio_path: 참조 오디오 경로 (None이면 자동 선택)
            ref_text: 참조 텍스트 (None이면 자동 선택)
            add_padding: 앞에 무음 패딩 추가 여부 (첫 세그먼트만 True)

        Returns:
            WAV 오디오 데이터 또는 None
        """
        # 텍스트 전처리: 조기 EOS 방지를 위한 패딩
        # 문장 끝에 마침표가 없으면 추가하고, 공백 패딩 추가
        text = text.strip()
        if text and not text[-1] in ".。!！?？…~～":
            text = text + "."
        # 끝에 공백 패딩 추가 (모델이 문장 끝을 더 명확히 인식)
        text = text + "  "

        # 참조 오디오가 전달되지 않으면 자동 선택
        if ref_audio_path is None or ref_text is None:
            ref_audio_path, ref_text = self._select_reference_audio(char_id, len(text))

        if not ref_audio_path.exists():
            logger.error(f"참조 오디오가 없습니다: {char_id}")
            return None

        # 추가 참조 오디오
        aux_refs = self._get_aux_reference_audios(char_id, ref_audio_path)

        # prompt_text: 참조 텍스트 사용 (품질 유지)
        prompt_text = ref_text

        # 디버깅용 로깅: 실제 API로 전송되는 참조 정보
        logger.info(f"[합성] === API 요청 파라미터 ===")
        logger.info(f"[합성] 목표 텍스트: {text}")
        logger.info(f"[합성] 참조 오디오: {ref_audio_path.name}")
        logger.info(f"[합성] 참조 텍스트: {prompt_text}")

        # GPT-SoVITS v2 언어 코드 변환
        lang_map = {
            "ko": "all_ko",
            "ja": "all_ja",
            "zh": "all_zh",
            "en": "all_en",
        }
        api_lang = lang_map.get(language, language)

        # text_split_method: cut0=분할없음, cut5=문장부호 분할
        # 짧은 텍스트는 분할하지 않음 (조기 EOS 방지)
        split_method = "cut0" if len(text) < 80 else "cut5"

        params = {
            "text": text,
            "text_lang": api_lang,
            "ref_audio_path": str(ref_audio_path.absolute()),
            "aux_ref_audio_paths": aux_refs,
            "prompt_text": prompt_text,
            "prompt_lang": api_lang,
            "top_k": top_k,
            "top_p": top_p,
            "temperature": temperature,
            "repetition_penalty": 1.3,  # 적절한 반복 억제
            "text_split_method": split_method,
            "speed_factor": speed_factor,
            "batch_size": 1,  # 안정적인 출력을 위해 배치 크기 1
        }

        import time

        start_time = time.time()

        connector = aiohttp.TCPConnector(force_close=True)
        timeout = aiohttp.ClientTimeout(total=90)

        try:
            async with aiohttp.ClientSession(
                connector=connector, timeout=timeout
            ) as session:
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

                    # 스피커 절전 모드로 인한 앞부분 잘림 방지 (첫 세그먼트만)
                    if add_padding:
                        audio_data = add_silence_padding(audio_data, silence_ms=150)

                    logger.debug(
                        f"[합성] 세그먼트 완료 ({elapsed:.1f}초, {len(audio_data):,} bytes)"
                    )

                    await asyncio.sleep(0.3)
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
        speed_factor: float = 1.0,
        top_k: int = 12,  # 안정성 (5~15 권장)
        top_p: float = 1.0,
        temperature: float = 0.9,  # 약간만 높임 (0.8→0.9)
    ) -> bool:
        """텍스트를 음성으로 합성하여 파일로 저장

        Args:
            text: 합성할 텍스트
            char_id: 캐릭터 ID
            output_path: 출력 파일 경로
            language: 텍스트 언어
            speed_factor: 음성 속도 (0.5~2.0)
            top_k: 샘플링 다양성 (1~20)
            top_p: Nucleus sampling (0.1~1.0)
            temperature: 음성 랜덤성 (0.1~2.0)

        Returns:
            bool: 성공 여부
        """
        audio_data = await self.synthesize(
            text,
            char_id,
            language,
            speed_factor=speed_factor,
            top_k=top_k,
            top_p=top_p,
            temperature=temperature,
        )
        if audio_data is None:
            return False

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(audio_data)
        return True
