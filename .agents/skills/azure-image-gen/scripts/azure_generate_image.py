#!/usr/bin/env python3
"""
Generate images using Azure OpenAI gpt-image-1.5 deployment.

Requires:
  - AZURE_OPENAI_ENDPOINT  (e.g. https://<resource>.openai.azure.com)
  - AZURE_OPENAI_API_KEY
"""

import sys
import json
import base64
import argparse
import io
import os
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Environment / .env helpers
# ---------------------------------------------------------------------------

def _read_env_file() -> dict[str, str]:
    """Read key=value pairs from .env files in current or parent directories."""
    current_dir = Path.cwd()
    for parent in [current_dir] + list(current_dir.parents):
        env_file = parent / ".env"
        if env_file.exists():
            pairs: dict[str, str] = {}
            with open(env_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        k, v = line.split("=", 1)
                        pairs[k.strip()] = v.strip().strip("\"'")
            return pairs
    return {}


def _resolve_env(name: str) -> Optional[str]:
    """Return env var value, falling back to .env file."""
    val = os.environ.get(name)
    if val:
        return val
    return _read_env_file().get(name)


# ---------------------------------------------------------------------------
# Image saving / post-processing  (shared with generate-image skill)
# ---------------------------------------------------------------------------

MAX_WIDTH = 500
TARGET_FILE_SIZE_KB = 200
MAX_FILE_SIZE_KB = 220
MIN_JPEG_QUALITY = 25
MIN_WEBP_QUALITY = 35
QUALITY_STEP = 5
RESIZE_SCALE_STEP = 0.9
MIN_WIDTH = 320
COMPLEXITY_WEBP_THRESHOLD = 0.42


def resize_and_compress_image(output_path: str) -> str:
    """Resize to max 500 px width and compress toward ~200 KB for blog covers."""
    try:
        from PIL import Image, ImageFilter, ImageStat
    except ImportError:
        print("⚠️  Pillow not installed; skipping resize/compress. Install with: pip install Pillow")
        return output_path

    def detect_transparency(image):
        if "A" not in image.getbands():
            return False
        return image.getchannel("A").getextrema()[0] < 255

    def analyze_image_complexity(image):
        sample = image.convert("RGB")
        sample.thumbnail((256, 256), Image.LANCZOS)
        grayscale = sample.convert("L")
        grayscale_stat = ImageStat.Stat(grayscale)
        contrast = grayscale_stat.stddev[0]
        edges = grayscale.filter(ImageFilter.FIND_EDGES)
        edge_mean = ImageStat.Stat(edges).mean[0]
        color_stddev = sum(ImageStat.Stat(sample).stddev) / 3
        complexity = min(
            1.0,
            (contrast / 90.0) * 0.35
            + (edge_mean / 80.0) * 0.45
            + (color_stddev / 90.0) * 0.20,
        )
        return {"score": complexity, "contrast": contrast, "edge_mean": edge_mean}

    def choose_preferred_format(image, metrics):
        return "JPEG", f"complexity score {metrics['score']:.2f}"

    def encode_candidate(image, fmt, quality):
        candidate = image
        buf = io.BytesIO()
        if fmt == "JPEG":
            if candidate.mode not in ("RGB", "L"):
                candidate = candidate.convert("RGB")
            candidate.save(buf, format="JPEG", quality=quality, optimize=True, progressive=True)
        elif fmt == "WEBP":
            if candidate.mode not in ("RGB", "RGBA", "L"):
                candidate = candidate.convert("RGBA" if detect_transparency(candidate) else "RGB")
            candidate.save(buf, format="WEBP", quality=quality, method=6)
        else:
            raise ValueError(f"Unsupported format: {fmt}")
        data = buf.getvalue()
        return data, len(data) / 1024

    def build_best_variant(image, fmt):
        min_quality = MIN_WEBP_QUALITY if fmt == "WEBP" else MIN_JPEG_QUALITY
        start_quality = 90 if fmt == "WEBP" else 85
        working_img = image
        best_variant = None
        while True:
            quality = start_quality
            while quality >= min_quality:
                candidate_data, candidate_size_kb = encode_candidate(working_img, fmt, quality)
                candidate = {
                    "format": fmt,
                    "data": candidate_data,
                    "size_kb": candidate_size_kb,
                    "quality": quality,
                    "width": working_img.width,
                    "height": working_img.height,
                }
                if best_variant is None or candidate_size_kb < best_variant["size_kb"]:
                    best_variant = candidate
                if candidate_size_kb <= MAX_FILE_SIZE_KB:
                    return candidate
                quality -= QUALITY_STEP
            next_width = int(working_img.width * RESIZE_SCALE_STEP)
            if next_width < MIN_WIDTH or next_width >= working_img.width:
                return best_variant
            next_height = max(1, int(working_img.height * (next_width / working_img.width)))
            working_img = working_img.resize((next_width, next_height), Image.LANCZOS)
            print(
                f"🪶 Reducing dimensions to {next_width}x{next_height} "
                f"while testing {fmt} to approach {TARGET_FILE_SIZE_KB}KB"
            )

    path = Path(output_path)
    img = Image.open(path)

    if img.width > MAX_WIDTH:
        ratio = MAX_WIDTH / img.width
        new_height = int(img.height * ratio)
        img = img.resize((MAX_WIDTH, new_height), Image.LANCZOS)
        print(f"📐 Resized to {MAX_WIDTH}x{new_height}")

    img.save(output_path, optimize=True)
    file_size_kb = path.stat().st_size / 1024

    if file_size_kb <= MAX_FILE_SIZE_KB:
        print(f"📦 File size: {file_size_kb:.1f}KB")
        return output_path

    metrics = analyze_image_complexity(img)
    preferred_format, reason = choose_preferred_format(img, metrics)
    alternate_format = "JPEG" if preferred_format == "WEBP" else "WEBP"
    print(
        f"🧠 Preferred cover format: {preferred_format} "
        f"({reason}; edge mean {metrics['edge_mean']:.1f}, contrast {metrics['contrast']:.1f})"
    )

    preferred_variant = build_best_variant(img, preferred_format)
    alternate_variant = None  # WebP disabled; always output JPEG

    chosen_variant = preferred_variant
    if alternate_variant is not None:
        preferred_over_limit = preferred_variant["size_kb"] > MAX_FILE_SIZE_KB
        alternate_hits_target = alternate_variant["size_kb"] <= MAX_FILE_SIZE_KB
        alternate_meaningfully_smaller = alternate_variant["size_kb"] + 15 < preferred_variant["size_kb"]
        if (preferred_over_limit and alternate_hits_target) or alternate_meaningfully_smaller:
            chosen_variant = alternate_variant
            print(
                f"🔁 Switching to {alternate_variant['format']} "
                f"({alternate_variant['size_kb']:.1f}KB vs {preferred_variant['size_kb']:.1f}KB)"
            )

    extension = ".webp" if chosen_variant["format"] == "WEBP" else ".jpg"
    final_path = str(path.with_suffix(extension))

    with open(final_path, "wb") as f:
        f.write(chosen_variant["data"])

    print(
        f"🗜️  Saved cover as {chosen_variant['format']} "
        f"(quality={chosen_variant['quality']}, {chosen_variant['width']}x{chosen_variant['height']}): "
        f"{chosen_variant['size_kb']:.1f}KB → {final_path}"
    )

    if chosen_variant["size_kb"] > MAX_FILE_SIZE_KB:
        print(
            f"⚠️  Final size still above ~{TARGET_FILE_SIZE_KB}KB target: "
            f"{chosen_variant['size_kb']:.1f}KB"
        )

    if path.exists() and final_path != output_path:
        path.unlink()

    return final_path


# ---------------------------------------------------------------------------
# Azure OpenAI image generation
# ---------------------------------------------------------------------------

DEFAULT_DEPLOYMENT = "gpt-image-1.5"
DEFAULT_API_VERSION = "2024-02-01"


def generate_image(
    prompt: str,
    *,
    endpoint: Optional[str] = None,
    api_key: Optional[str] = None,
    deployment: str = DEFAULT_DEPLOYMENT,
    api_version: str = DEFAULT_API_VERSION,
    output_path: str = "generated_image.png",
    size: str = "1024x1024",
    quality: str = "medium",
    output_format: str = "png",
    output_compression: int = 100,
    n: int = 1,
) -> str:
    """Call Azure OpenAI Images API and save the first image to *output_path*.

    Returns the final (possibly post-processed) file path.
    """
    try:
        import requests
    except ImportError:
        print("❌ Error: 'requests' library not found. Install with: pip install requests")
        sys.exit(1)

    # Resolve credentials
    if not api_key:
        api_key = _resolve_env("AZURE_OPENAI_API_KEY")
    if not api_key:
        print("❌ Error: AZURE_OPENAI_API_KEY not found!")
        print("\nSet it via environment variable or .env file:")
        print("  AZURE_OPENAI_API_KEY=your-key-here")
        sys.exit(1)

    if not endpoint:
        endpoint = _resolve_env("AZURE_OPENAI_ENDPOINT")
    if not endpoint:
        print("❌ Error: AZURE_OPENAI_ENDPOINT not found!")
        print("\nSet it via environment variable or .env file:")
        print("  AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com")
        sys.exit(1)

    endpoint = endpoint.rstrip("/")

    url = f"{endpoint}/openai/deployments/{deployment}/images/generations?api-version={api_version}"

    payload = {
        "prompt": prompt,
        "size": size,
        "quality": quality,
        "output_format": output_format,
        "output_compression": output_compression,
        "n": n,
    }

    print(f"🎨 Generating image via Azure OpenAI ({deployment})")
    print(f"📝 Prompt: {prompt}")
    print(f"📐 Size: {size}  Quality: {quality}  Format: {output_format}")

    response = requests.post(
        url,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        json=payload,
        timeout=120,
    )

    if response.status_code != 200:
        print(f"❌ API Error ({response.status_code}): {response.text}")
        sys.exit(1)

    result = response.json()

    # Azure returns { data: [ { b64_json: "..." } ] }
    data_list = result.get("data", [])
    if not data_list:
        print("❌ No images returned in the response")
        print(f"Response: {json.dumps(result, indent=2)}")
        sys.exit(1)

    b64 = data_list[0].get("b64_json")
    if not b64:
        print("❌ No b64_json found in response data[0]")
        print(f"Response data[0]: {json.dumps(data_list[0], indent=2)}")
        sys.exit(1)

    image_bytes = base64.b64decode(b64)
    with open(output_path, "wb") as f:
        f.write(image_bytes)

    print(f"💾 Raw image saved to: {output_path}")

    final_path = resize_and_compress_image(output_path)
    print(f"✅ Final image: {final_path}")
    return final_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Generate images with Azure OpenAI gpt-image-1.5",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  python azure_generate_image.py "A red fox in an autumn forest"
  python azure_generate_image.py "Abstract art" --size 1536x1024
  python azure_generate_image.py "Logo design" --quality high --output logo.png
  python azure_generate_image.py "Banner" --format png --compression 80
""",
    )

    parser.add_argument("prompt", help="Text description of the image to generate")
    parser.add_argument("--output", "-o", default="generated_image.png", help="Output file path (default: generated_image.png)")
    parser.add_argument("--size", "-s", default="1024x1024", choices=["1024x1024", "1024x1536", "1536x1024", "auto"], help="Image size (default: 1024x1024)")
    parser.add_argument("--quality", "-q", default="medium", choices=["low", "medium", "high"], help="Image quality (default: medium)")
    parser.add_argument("--format", "-f", default="png", choices=["png", "jpeg", "webp"], help="Output format from API (default: png)")
    parser.add_argument("--compression", type=int, default=100, help="Output compression 0-100 (default: 100, lossless)")
    parser.add_argument("--n", type=int, default=1, help="Number of images (default: 1)")
    parser.add_argument("--deployment", "-d", default=DEFAULT_DEPLOYMENT, help=f"Azure deployment name (default: {DEFAULT_DEPLOYMENT})")
    parser.add_argument("--api-version", default=DEFAULT_API_VERSION, help=f"API version (default: {DEFAULT_API_VERSION})")
    parser.add_argument("--endpoint", help="Azure OpenAI endpoint URL (overrides env)")
    parser.add_argument("--api-key", help="Azure OpenAI API key (overrides env)")

    args = parser.parse_args()

    generate_image(
        args.prompt,
        endpoint=args.endpoint,
        api_key=args.api_key,
        deployment=args.deployment,
        api_version=args.api_version,
        output_path=args.output,
        size=args.size,
        quality=args.quality,
        output_format=args.format,
        output_compression=args.compression,
        n=args.n,
    )


if __name__ == "__main__":
    main()
