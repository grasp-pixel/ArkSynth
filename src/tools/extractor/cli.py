"""
CLI for Arknights Voice Extractor.

Usage:
    uv run python -m tools.extractor [options]
"""
import argparse
import sys
from pathlib import Path

from .core import extract_all_voices


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Extract Arknights voice files from AssetBundle",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m tools.extractor
  python -m tools.extractor --lang voice_kr
  python -m tools.extractor --input ./VoiceAssets --output ./extracted
        """,
    )

    parser.add_argument(
        "--input", "-i",
        type=Path,
        default=Path("VoiceAssets"),
        help="Input directory containing voice folders (default: VoiceAssets)",
    )

    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=Path("extracted"),
        help="Output directory (default: extracted)",
    )

    parser.add_argument(
        "--lang", "-l",
        type=str,
        nargs="+",
        default=None,
        help="Languages to extract (default: voice, voice_cn, voice_en, voice_kr)",
    )

    parser.add_argument(
        "--format", "-f",
        type=str,
        default="mp3",
        choices=["mp3", "wav", "ogg"],
        help="Output audio format (default: mp3)",
    )

    args = parser.parse_args(argv)

    if not args.input.exists():
        print(f"Error: Input directory not found: {args.input}")
        return 1

    print("=" * 60)
    print("Arknights Voice Extractor")
    print("=" * 60)
    print(f"Input:  {args.input.absolute()}")
    print(f"Output: {args.output.absolute()}")
    print(f"Format: {args.format}")
    print(f"Languages: {args.lang or ['voice', 'voice_cn', 'voice_en', 'voice_kr']}")
    print("=" * 60)

    stats = extract_all_voices(
        args.input,
        args.output,
        args.format,
        args.lang,
    )

    print("\n" + "=" * 60)
    print("EXTRACTION COMPLETE")
    print("=" * 60)

    total_extracted = 0
    total_failed = 0

    for lang, s in stats.items():
        print(f"  {lang}: {s['extracted']} audio files ({s['failed']} failed)")
        total_extracted += s["extracted"]
        total_failed += s["failed"]

    print("-" * 60)
    print(f"  Total: {total_extracted} audio files extracted")

    if total_failed > 0:
        print(f"  Warning: {total_failed} files failed to process")

    return 0


if __name__ == "__main__":
    sys.exit(main())
