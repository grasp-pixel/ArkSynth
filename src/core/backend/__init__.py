"""ArkSynth 백엔드 서버"""

import asyncio

# === 전역 GPU 세마포어 ===
# TTS(GPT-SoVITS)와 OCR(EasyOCR)이 동시에 GPU를 사용하면 메모리 부족 크래시 발생
# 동시에 하나의 GPU 작업만 실행되도록 제한
_gpu_semaphore: asyncio.Semaphore | None = None


def get_gpu_semaphore() -> asyncio.Semaphore:
    """전역 GPU 세마포어 반환 (lazy init)"""
    global _gpu_semaphore
    if _gpu_semaphore is None:
        _gpu_semaphore = asyncio.Semaphore(1)
        print("[Backend] GPU 세마포어 초기화 (동시 실행 1개 제한)", flush=True)
    return _gpu_semaphore
