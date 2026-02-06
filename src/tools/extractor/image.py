"""
Arknights image extractor core logic.
Extracts images (Texture2D, Sprite) from AssetBundle files.
"""
import re
from pathlib import Path

import UnityPy
from PIL import Image
from UnityPy.enums.BundleFile import CompressionFlags
from UnityPy.helpers import CompressionHelper

from .lz4ak import decompress_lz4ak

# Register LZ4AK decompression for Arknights
CompressionHelper.DECOMPRESSION_MAP[CompressionFlags.LZHAM] = decompress_lz4ak

# 메인 이미지 최소 크기 (조각 이미지 제외)
MIN_IMAGE_SIZE = 512


def get_folder_name(ab_stem: str) -> str:
    """
    번들 파일명에서 폴더명 추출 (분할 번호 제거).

    Examples:
        avg_npc_023_2 → npc_023
        avg_002_amiya_1 → amiya
        avgnew_112_siege_1 → siege
        char_002_amiya_1 → amiya
        char_002_amiya_summer_2 → amiya
        avg_char_501_durin_1 → durin
    """
    # 마지막 _N (분할 번호) 제거
    stem = re.sub(r'_\d+$', '', ab_stem)

    # avg_npc_XXX → npc_XXX
    if match := re.match(r'avg_(npc_\d+)', stem):
        return match.group(1)

    # avg_char_XXX_charname → charname
    if match := re.match(r'avg_char_\d+_([a-z]+\d*)', stem):
        return match.group(1)

    # avg_XXX_charname 또는 avgnew_XXX_charname → charname
    if match := re.match(r'(?:avg|avgnew)_\d+_([a-z]+\d*)', stem):
        return match.group(1)

    # char_XXX_charname 또는 char_XXX_charname_skin → charname
    if match := re.match(r'char_\d+_([a-z]+\d*)', stem):
        return match.group(1)

    # 매칭 안 되면 원본 반환
    return stem


def crop_transparent(image: Image.Image, padding: int = 0) -> Image.Image:
    """투명 영역을 제거하고 콘텐츠만 크롭"""
    if image.mode != "RGBA":
        return image

    bbox = image.getbbox()
    if bbox is None:
        return image

    # 패딩 적용
    if padding > 0:
        left = max(0, bbox[0] - padding)
        upper = max(0, bbox[1] - padding)
        right = min(image.width, bbox[2] + padding)
        lower = min(image.height, bbox[3] + padding)
        bbox = (left, upper, right, lower)

    return image.crop(bbox)


def apply_alpha_mask(image: Image.Image, alpha_mask: Image.Image) -> Image.Image:
    """알파 마스크를 이미지에 적용"""
    if image.mode != "RGBA":
        image = image.convert("RGBA")

    # 알파 마스크를 그레이스케일로 변환
    if alpha_mask.mode != "L":
        alpha_mask = alpha_mask.convert("L")

    # 크기가 다르면 리사이즈
    if alpha_mask.size != image.size:
        alpha_mask = alpha_mask.resize(image.size, Image.Resampling.LANCZOS)

    # 알파 채널 적용
    r, g, b, _ = image.split()
    return Image.merge("RGBA", (r, g, b, alpha_mask))


def extract_images_from_bundle(
    ab_path: Path,
    output_dir: Path,
    output_format: str = "png",
) -> tuple[list[Path], list[Path]]:
    """
    Extract images from an AssetBundle.

    Args:
        ab_path: Path to the .ab file
        output_dir: Output directory for extracted images
        output_format: Output format (png, jpg, webp)

    Returns:
        Tuple of (extracted file paths, skipped file paths)
    """
    extracted = []
    skipped = []

    try:
        env = UnityPy.load(str(ab_path))
    except Exception as e:
        print(f"Failed to load {ab_path}: {e}")
        return extracted, skipped

    # 폴더명 추출 (분할 번호 제거)
    folder_name = get_folder_name(ab_path.stem)
    char_dir = output_dir / folder_name
    char_dir.mkdir(parents=True, exist_ok=True)

    # 1단계: 모든 이미지 수집 (이름 -> PIL Image)
    images: dict[str, Image.Image] = {}

    for obj in env.objects:
        if obj.type.name not in ("Texture2D", "Sprite"):
            continue

        try:
            data = obj.read()
            img_name = getattr(data, 'm_Name', None) or getattr(data, 'name', 'unknown')

            if obj.type.name == "Sprite":
                image = data.image
            else:
                image = data.image

            if image is None:
                continue

            # 메인 이미지만 (512x512 이상)
            if image.width < MIN_IMAGE_SIZE or image.height < MIN_IMAGE_SIZE:
                continue

            images[img_name] = image

        except Exception as e:
            print(f"  Warning: Failed to read {obj.type.name}: {e}")
            continue

    # 2단계: 알파 마스크 적용, 크롭, 저장
    processed = set()
    skipped = []

    for img_name, image in images.items():
        # 알파 마스크는 건너뜀 (메인 이미지에 적용할 것)
        if "[alpha]" in img_name:
            continue

        # 이미 처리됨
        if img_name in processed:
            continue

        # 대응하는 알파 마스크 찾기
        alpha_name = f"{img_name}[alpha]"
        if alpha_name in images:
            image = apply_alpha_mask(image, images[alpha_name])
        else:
            # 폴백: #1 변형의 알파 마스크 사용 (기본 이미지에 알파가 없는 경우)
            fallback_alpha = f"{img_name}#1[alpha]"
            if fallback_alpha in images:
                image = apply_alpha_mask(image, images[fallback_alpha])

        # 투명 영역 크롭
        image = crop_transparent(image, padding=4)

        out_path = char_dir / f"{img_name}.{output_format}"

        if out_path.exists():
            skipped.append(out_path)
            processed.add(img_name)
            continue

        image.save(out_path)
        extracted.append(out_path)
        processed.add(img_name)

    return extracted, skipped


def extract_image_folder(
    source_dir: Path,
    output_dir: Path,
    output_format: str = "png",
) -> dict[str, int]:
    """
    Extract all images from a folder of .ab files.

    Args:
        source_dir: Directory containing .ab files
        output_dir: Output directory
        output_format: Output format

    Returns:
        Dictionary with extraction statistics
    """
    stats = {"processed": 0, "extracted": 0, "skipped": 0, "failed": 0}

    ab_files = list(source_dir.glob("*.ab"))
    total = len(ab_files)

    for i, ab_path in enumerate(ab_files, 1):
        print(f"[{i}/{total}] Processing {ab_path.name}...")

        try:
            extracted, skipped = extract_images_from_bundle(ab_path, output_dir, output_format)
            stats["processed"] += 1
            stats["extracted"] += len(extracted)
            stats["skipped"] += len(skipped)

            if extracted or skipped:
                print(f"  -> Extracted {len(extracted)}, Skipped {len(skipped)} images")
        except Exception as e:
            print(f"  -> Failed: {e}")
            stats["failed"] += 1

    return stats


def extract_avg_characters(
    image_assets_dir: Path,
    output_dir: Path,
    output_format: str = "png",
) -> dict[str, int]:
    """
    Extract character images from avg/characters directory.

    Args:
        image_assets_dir: Path to ImageAssets directory
        output_dir: Output directory
        output_format: Output format (png, jpg, webp)

    Returns:
        Extraction statistics
    """
    characters_dir = image_assets_dir / "avg" / "characters"

    if not characters_dir.exists():
        print(f"Error: Directory not found: {characters_dir}")
        return {"processed": 0, "extracted": 0, "failed": 0}

    print(f"\n{'='*50}")
    print(f"Extracting character images...")
    print(f"Source: {characters_dir}")
    print(f"Output: {output_dir}")
    print(f"{'='*50}\n")

    return extract_image_folder(characters_dir, output_dir, output_format)


if __name__ == "__main__":
    import sys

    # Quick test
    # Bundle location: files/bundles/avg/characters -> Assets/Image/avg/characters
    image_assets = Path("Assets/Image")
    output = Path("extracted/images/characters")

    if len(sys.argv) > 1:
        image_assets = Path(sys.argv[1])
    if len(sys.argv) > 2:
        output = Path(sys.argv[2])

    stats = extract_avg_characters(image_assets, output)
    print(f"\nComplete: {stats['extracted']} images extracted")
