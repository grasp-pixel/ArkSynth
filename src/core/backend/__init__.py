"""ArkSynth 백엔드 서버"""

import asyncio
from contextlib import asynccontextmanager

# === 전역 GPU 세마포어 ===
# TTS(GPT-SoVITS)와 OCR(EasyOCR)이 동시에 GPU를 사용하면 메모리 부족 크래시 발생
# 동시에 하나의 GPU 작업만 실행되도록 제한
_gpu_semaphore: asyncio.Semaphore | None = None
_gpu_semaphore_enabled: bool = True  # 세마포어 활성화 여부


def get_gpu_semaphore() -> asyncio.Semaphore:
    """전역 GPU 세마포어 반환 (lazy init)"""
    global _gpu_semaphore
    if _gpu_semaphore is None:
        _gpu_semaphore = asyncio.Semaphore(1)
        print("[Backend] GPU 세마포어 초기화 (동시 실행 1개 제한)", flush=True)
    return _gpu_semaphore


def is_gpu_semaphore_enabled() -> bool:
    """GPU 세마포어 활성화 여부 반환"""
    return _gpu_semaphore_enabled


def set_gpu_semaphore_enabled(enabled: bool) -> None:
    """GPU 세마포어 활성화/비활성화"""
    global _gpu_semaphore_enabled
    _gpu_semaphore_enabled = enabled
    print(f"[Backend] GPU 세마포어 {'활성화' if enabled else '비활성화'}", flush=True)


@asynccontextmanager
async def gpu_semaphore_context():
    """GPU 세마포어 컨텍스트 (비활성화 시 바로 통과)"""
    if _gpu_semaphore_enabled:
        sem = get_gpu_semaphore()
        async with sem:
            yield
    else:
        yield
