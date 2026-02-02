"""
Arknights AssetBundle Voice Extractor

Usage:
    from tools.extractor import extract_audio_from_bundle, extract_all_voices
"""
from .core import (
    extract_audio_from_bundle,
    extract_voice_folder,
    extract_all_voices,
)

__all__ = [
    "extract_audio_from_bundle",
    "extract_voice_folder",
    "extract_all_voices",
]
