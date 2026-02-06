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


def _extract_skin_suffix(char_name: str) -> tuple[str, str]:
    """캐릭터 이름에서 스킨 접미사 추출

    Args:
        char_name: 캐릭터 이름 (예: char_003_kalts_boc#6)

    Returns:
        (기본 캐릭터 이름, 스킨 접미사) 튜플
        예: ("char_003_kalts", "_boc6")
        스킨이 없으면 ("char_003_kalts", "")
    """
    # 스킨 패턴: _boc#6, _epoque#34, _iteration#2 등
    match = re.search(r'_([a-z]+)#(\d+)$', char_name)
    if match:
        base_char = char_name[:match.start()]
        skin_type = match.group(1)  # boc, epoque, iteration 등
        skin_num = match.group(2)   # 6, 34, 2 등
        # # 제거하여 파일명 안전하게
        skin_suffix = f"_{skin_type}{skin_num}"
        return base_char, skin_suffix
    return char_name, ""


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

    # 캐릭터 이름과 스킨 접미사 추출
    char_name = ab_path.stem
    base_char, skin_suffix = _extract_skin_suffix(char_name)

    # 기본 캐릭터 폴더에 저장 (스킨도 같은 폴더)
    char_dir = output_dir / base_char
    char_dir.mkdir(parents=True, exist_ok=True)

    for obj in env.objects:
        if obj.type.name != "AudioClip":
            continue

        try:
            audio = obj.read()

            # 실제 오디오 이름 가져오기 (m_Name 속성 사용)
            audio_name = getattr(audio, 'm_Name', None) or getattr(audio, 'name', None)

            samples = getattr(audio, 'samples', None)

            if samples:
                for sample_name, data in samples.items():
                    if data:
                        # 실제 이름 사용 (sample_name 또는 audio.m_Name)
                        actual_name = sample_name or audio_name or "unknown"
                        # 확장자 제거 후 스킨 접미사 + 새 확장자 추가
                        base_name = Path(actual_name).stem
                        out_name = f"{base_name}{skin_suffix}.{output_format}"
                        out_path = char_dir / out_name

                        with open(out_path, 'wb') as f:
                            f.write(data)

                        extracted.append(out_path)
            else:
                m_AudioData = getattr(audio, 'm_AudioData', None)
                if m_AudioData:
                    # 실제 이름 사용 + 스킨 접미사
                    actual_name = audio_name or "unknown"
                    base_name = Path(actual_name).stem
                    out_name = f"{base_name}{skin_suffix}.{output_format}"
                    out_path = char_dir / out_name

                    with open(out_path, 'wb') as f:
                        f.write(m_AudioData)

                    extracted.append(out_path)

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
        languages = ["voice_kr"]

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
