"""
Arknights voice extractor core logic.
Extracts audio files from AssetBundle files in arknights-audio format.
"""
import re
from pathlib import Path
from typing import Optional

import UnityPy
from UnityPy.enums.BundleFile import CompressionFlags
from UnityPy.helpers import CompressionHelper

from .lz4ak import decompress_lz4ak

# Register LZ4AK decompression for Arknights
CompressionHelper.DECOMPRESSION_MAP[CompressionFlags.LZHAM] = decompress_lz4ak


def extract_audio_from_bundle(
    ab_path: Path,
    output_dir: Path,
    output_format: str = "mp3",
) -> list[Path]:
    """
    Extract audio files from an AssetBundle.

    Args:
        ab_path: Path to the .ab file
        output_dir: Output directory for extracted audio
        output_format: Output format (mp3, wav, ogg)

    Returns:
        List of extracted file paths
    """
    extracted = []

    try:
        env = UnityPy.load(str(ab_path))
    except Exception as e:
        print(f"Failed to load {ab_path}: {e}")
        return extracted

    # Get character folder name from ab filename
    char_name = ab_path.stem
    # Remove skin suffixes like _boc#6, _iteration#2, _epoque#34
    base_char = re.sub(r'_[a-z]+#\d+$', '', char_name)

    char_dir = output_dir / base_char
    char_dir.mkdir(parents=True, exist_ok=True)

    audio_index = 1
    for obj in env.objects:
        if obj.type.name != "AudioClip":
            continue

        try:
            audio = obj.read()
            samples = getattr(audio, 'samples', None)

            if samples:
                for name, data in samples.items():
                    if data:
                        out_name = f"CN_{audio_index:03d}.{output_format}"
                        out_path = char_dir / out_name

                        with open(out_path, 'wb') as f:
                            f.write(data)

                        extracted.append(out_path)
                        audio_index += 1
            else:
                m_AudioData = getattr(audio, 'm_AudioData', None)
                if m_AudioData:
                    out_name = f"CN_{audio_index:03d}.{output_format}"
                    out_path = char_dir / out_name

                    with open(out_path, 'wb') as f:
                        f.write(m_AudioData)

                    extracted.append(out_path)
                    audio_index += 1

        except Exception as e:
            print(f"Failed to extract audio from {ab_path}: {e}")
            continue

    return extracted


def extract_voice_folder(
    source_dir: Path,
    output_dir: Path,
    output_format: str = "mp3",
) -> dict[str, int]:
    """
    Extract all voice files from a folder.

    Args:
        source_dir: Directory containing .ab files
        output_dir: Output directory
        output_format: Output format

    Returns:
        Dictionary with extraction statistics
    """
    stats = {"processed": 0, "extracted": 0, "failed": 0}

    ab_files = list(source_dir.glob("*.ab"))
    total = len(ab_files)

    for i, ab_path in enumerate(ab_files, 1):
        print(f"[{i}/{total}] Processing {ab_path.name}...")

        try:
            extracted = extract_audio_from_bundle(ab_path, output_dir, output_format)
            stats["processed"] += 1
            stats["extracted"] += len(extracted)

            if extracted:
                print(f"  -> Extracted {len(extracted)} audio files")
        except Exception as e:
            print(f"  -> Failed: {e}")
            stats["failed"] += 1

    return stats


def extract_all_voices(
    voice_assets_dir: Path,
    output_dir: Path,
    output_format: str = "mp3",
    languages: Optional[list[str]] = None,
) -> dict[str, dict[str, int]]:
    """
    Extract all voice files from VoiceAssets directory.

    Args:
        voice_assets_dir: Path to VoiceAssets directory
        output_dir: Output directory
        output_format: Output format
        languages: List of language folders to process (default: all)

    Returns:
        Dictionary with stats per language
    """
    if languages is None:
        languages = ["voice", "voice_cn", "voice_en", "voice_kr"]

    all_stats = {}

    for lang in languages:
        lang_source = voice_assets_dir / lang
        if not lang_source.exists():
            print(f"Skipping {lang}: directory not found")
            continue

        print(f"\n{'='*50}")
        print(f"Processing {lang}...")
        print(f"{'='*50}")

        lang_output = output_dir / lang
        stats = extract_voice_folder(lang_source, lang_output, output_format)
        all_stats[lang] = stats

        print(f"\n{lang} complete: {stats['processed']} files, {stats['extracted']} audio extracted")

    return all_stats
