"""TTS 공통 모듈

여러 TTS 엔진에서 공유하는 유틸리티 함수들.
"""

from .text_processor import preprocess_text_for_tts, split_text_for_tts, normalize_numbers_for_tts
from .audio_utils import add_silence_padding, concatenate_wav, get_audio_duration
from .reference_manager import (
    ReferenceManager,
    ReferenceAudio,
    VOICE_TITLE_PRIORITY,
    EXCLUDED_VOICE_TITLES,
    MIN_REF_TEXT_LENGTH,
    MAX_REF_TEXT_LENGTH,
    calculate_reference_score,
    calculate_qwen3_reference_score,
    is_excluded_voice,
    select_best_references,
    load_reference_info,
    select_reference_by_score,
    select_reference_hybrid,
    select_reference_for_qwen3,
    get_all_references_by_score,
)

__all__ = [
    # text_processor
    "preprocess_text_for_tts",
    "split_text_for_tts",
    "normalize_numbers_for_tts",
    # audio_utils
    "add_silence_padding",
    "concatenate_wav",
    "get_audio_duration",
    # reference_manager
    "ReferenceManager",
    "ReferenceAudio",
    "VOICE_TITLE_PRIORITY",
    "EXCLUDED_VOICE_TITLES",
    "MIN_REF_TEXT_LENGTH",
    "MAX_REF_TEXT_LENGTH",
    "calculate_reference_score",
    "calculate_qwen3_reference_score",
    "is_excluded_voice",
    "select_best_references",
    "load_reference_info",
    "select_reference_by_score",
    "select_reference_hybrid",
    "select_reference_for_qwen3",
    "get_all_references_by_score",
]
