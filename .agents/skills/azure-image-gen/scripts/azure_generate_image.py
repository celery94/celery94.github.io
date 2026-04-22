#!/usr/bin/env python3
"""
Generate or edit images with an Azure OpenAI GPT Image deployment.

Requires:
  - AZURE_OPENAI_ENDPOINT  (e.g. https://<resource>.openai.azure.com)
  - AZURE_OPENAI_API_KEY
"""

import argparse
import base64
import io
import json
import mimetypes
import os
import re
import sys
from contextlib import ExitStack
from pathlib import Path
from typing import Optional, Sequence


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
            with open(env_file, "r", encoding="utf-8") as f:
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
# Image saving / post-processing
# ---------------------------------------------------------------------------

MAX_WIDTH = 500
TARGET_FILE_SIZE_KB = 200
MAX_FILE_SIZE_KB = 220
MIN_JPEG_QUALITY = 25
MIN_WEBP_QUALITY = 35
QUALITY_STEP = 5
RESIZE_SCALE_STEP = 0.9
MIN_WIDTH = 320


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
    print(
        f"🧠 Preferred cover format: {preferred_format} "
        f"({reason}; edge mean {metrics['edge_mean']:.1f}, contrast {metrics['contrast']:.1f})"
    )

    chosen_variant = build_best_variant(img, preferred_format)
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
# Azure OpenAI image helpers
# ---------------------------------------------------------------------------

DEFAULT_DEPLOYMENT = "gpt-image-2"
DEFAULT_API_VERSION = "2025-04-01-preview"
DEFAULT_SIZE = "1024x1024"
DEFAULT_QUALITY = "medium"
DEFAULT_OUTPUT_FORMAT = "png"
DEFAULT_OUTPUT_COMPRESSION = 100
SIZE_PATTERN = re.compile(r"^\d+x\d+$")
FORMAT_SUFFIXES = {
    "png": {".png"},
    "jpeg": {".jpg", ".jpeg"},
    "webp": {".webp"},
}
PRIMARY_SUFFIX = {
    "png": ".png",
    "jpeg": ".jpg",
    "webp": ".webp",
}


def _existing_file(value: str) -> str:
    path = Path(value)
    if not path.is_file():
        raise argparse.ArgumentTypeError(f"File not found: {value}")
    return str(path)


def _parse_size(value: str) -> str:
    if value == "auto" or SIZE_PATTERN.fullmatch(value):
        return value
    raise argparse.ArgumentTypeError("size must be 'auto' or WIDTHxHEIGHT, for example 2048x1152")


def _parse_compression(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("compression must be an integer") from exc
    if not 0 <= parsed <= 100:
        raise argparse.ArgumentTypeError("compression must be between 0 and 100")
    return parsed


def _parse_image_count(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("n must be an integer") from exc
    if not 1 <= parsed <= 10:
        raise argparse.ArgumentTypeError("n must be between 1 and 10")
    return parsed


def _resolve_credentials(endpoint: Optional[str], api_key: Optional[str]) -> tuple[str, str]:
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

    return endpoint.rstrip("/"), api_key


def _build_headers(api_key: str, *, content_type: Optional[str] = None) -> dict[str, str]:
    headers = {"api-key": api_key}
    if content_type:
        headers["Content-Type"] = content_type
    return headers


def _build_operation_url(endpoint: str, deployment: str, api_version: str, operation: str) -> str:
    return f"{endpoint}/openai/deployments/{deployment}/images/{operation}?api-version={api_version}"


def _guess_mime_type(path: Path) -> str:
    mime_type, _ = mimetypes.guess_type(path.name)
    if mime_type and mime_type.startswith("image/"):
        return mime_type
    return "application/octet-stream"


def _build_generation_payload(
    prompt: str,
    *,
    size: str,
    quality: str,
    output_format: str,
    output_compression: int,
    n: int,
    background: Optional[str],
) -> dict[str, object]:
    payload: dict[str, object] = {
        "prompt": prompt,
        "size": size,
        "quality": quality,
        "output_format": output_format,
        "n": n,
    }
    if background:
        payload["background"] = background
    if output_format in {"jpeg", "webp"}:
        payload["output_compression"] = output_compression
    return payload


def _build_edit_form_data(
    prompt: str,
    *,
    size: str,
    quality: str,
    output_format: str,
    output_compression: int,
    n: int,
    background: Optional[str],
) -> dict[str, object]:
    data: dict[str, object] = {
        "prompt": prompt,
        "size": size,
        "quality": quality,
        "output_format": output_format,
        "n": n,
    }
    if background:
        data["background"] = background
    if output_format in {"jpeg", "webp"}:
        data["output_compression"] = output_compression
    return data


def _format_error_payload(payload: object) -> str:
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            code = error.get("code", "unknown_error")
            message = error.get("message", json.dumps(error, indent=2))
            return f"{code}: {message}"
        return json.dumps(payload, indent=2)
    return str(payload)


def _decode_response(response) -> dict[str, object]:
    if response.status_code != 200:
        try:
            payload = response.json()
            message = _format_error_payload(payload)
        except ValueError:
            message = response.text
        print(f"❌ API Error ({response.status_code}): {message}")
        sys.exit(1)

    try:
        result = response.json()
    except ValueError:
        print("❌ API Error: expected JSON response from Azure OpenAI")
        print(response.text)
        sys.exit(1)

    error = result.get("error")
    if error:
        print(f"❌ API Error: {_format_error_payload(result)}")
        sys.exit(1)

    return result


def _normalize_output_path(output_path: str, output_format: str) -> str:
    path = Path(output_path)
    valid_suffixes = FORMAT_SUFFIXES[output_format]
    if path.suffix.lower() in valid_suffixes:
        normalized = path
    else:
        normalized = path.with_suffix(PRIMARY_SUFFIX[output_format])
        print(f"ℹ️ Adjusted output extension to match {output_format}: {normalized}")

    if normalized.parent != Path("."):
        normalized.parent.mkdir(parents=True, exist_ok=True)
    return str(normalized)


def _extract_first_image(result: dict[str, object], output_path: str) -> tuple[bytes, dict[str, object]]:
    data_list = result.get("data")
    if not isinstance(data_list, list) or not data_list:
        print("❌ No images returned in the response")
        print(f"Response: {json.dumps(result, indent=2)}")
        sys.exit(1)

    if len(data_list) > 1:
        print(f"ℹ️ API returned {len(data_list)} images; saving only the first image to {output_path}")

    first = data_list[0]
    if not isinstance(first, dict):
        print("❌ Unexpected image payload format")
        print(f"Response data[0]: {json.dumps(first, indent=2)}")
        sys.exit(1)

    b64 = first.get("b64_json")
    if not isinstance(b64, str) or not b64:
        print("❌ No b64_json found in response data[0]")
        print(f"Response data[0]: {json.dumps(first, indent=2)}")
        sys.exit(1)

    try:
        image_bytes = base64.b64decode(b64)
    except ValueError:
        print("❌ Unable to decode b64_json from Azure response")
        sys.exit(1)

    return image_bytes, first


def _save_result_image(
    result: dict[str, object],
    *,
    output_path: str,
    output_format: str,
    post_process: bool,
) -> str:
    normalized_output_path = _normalize_output_path(output_path, output_format)
    image_bytes, image_data = _extract_first_image(result, normalized_output_path)

    revised_prompt = image_data.get("revised_prompt")
    if isinstance(revised_prompt, str) and revised_prompt:
        print(f"✍️ Revised prompt: {revised_prompt}")

    with open(normalized_output_path, "wb") as f:
        f.write(image_bytes)

    print(f"💾 Raw image saved to: {normalized_output_path}")

    if not post_process:
        print(f"✅ Final image: {normalized_output_path}")
        return normalized_output_path

    final_path = resize_and_compress_image(normalized_output_path)
    print(f"✅ Final image: {final_path}")
    return final_path


def generate_image(
    prompt: str,
    *,
    endpoint: Optional[str] = None,
    api_key: Optional[str] = None,
    deployment: str = DEFAULT_DEPLOYMENT,
    api_version: str = DEFAULT_API_VERSION,
    output_path: str = "generated_image.png",
    size: str = DEFAULT_SIZE,
    quality: str = DEFAULT_QUALITY,
    output_format: str = DEFAULT_OUTPUT_FORMAT,
    output_compression: int = DEFAULT_OUTPUT_COMPRESSION,
    n: int = 1,
    background: Optional[str] = None,
    post_process: bool = True,
) -> str:
    """Call the Azure OpenAI Images generations endpoint and save the first image."""
    try:
        import requests
    except ImportError:
        print("❌ Error: 'requests' library not found. Install with: pip install requests")
        sys.exit(1)

    endpoint, api_key = _resolve_credentials(endpoint, api_key)
    url = _build_operation_url(endpoint, deployment, api_version, "generations")
    payload = _build_generation_payload(
        prompt,
        size=size,
        quality=quality,
        output_format=output_format,
        output_compression=output_compression,
        n=n,
        background=background,
    )

    print(f"🎨 Generating image via Azure OpenAI ({deployment})")
    print(f"📝 Prompt: {prompt}")
    print(f"📐 Size: {size}  Quality: {quality}  Format: {output_format}")
    if background:
        print(f"🧱 Background: {background}")

    response = requests.post(
        url,
        headers=_build_headers(api_key, content_type="application/json"),
        json=payload,
        timeout=120,
    )
    result = _decode_response(response)
    return _save_result_image(
        result,
        output_path=output_path,
        output_format=output_format,
        post_process=post_process,
    )


def edit_image(
    prompt: str,
    *,
    input_images: Sequence[str],
    mask_path: Optional[str] = None,
    endpoint: Optional[str] = None,
    api_key: Optional[str] = None,
    deployment: str = DEFAULT_DEPLOYMENT,
    api_version: str = DEFAULT_API_VERSION,
    output_path: str = "generated_image.png",
    size: str = DEFAULT_SIZE,
    quality: str = DEFAULT_QUALITY,
    output_format: str = DEFAULT_OUTPUT_FORMAT,
    output_compression: int = DEFAULT_OUTPUT_COMPRESSION,
    n: int = 1,
    background: Optional[str] = None,
    post_process: bool = True,
) -> str:
    """Call the Azure OpenAI Images edits endpoint and save the first image."""
    try:
        import requests
    except ImportError:
        print("❌ Error: 'requests' library not found. Install with: pip install requests")
        sys.exit(1)

    endpoint, api_key = _resolve_credentials(endpoint, api_key)
    url = _build_operation_url(endpoint, deployment, api_version, "edits")
    data = _build_edit_form_data(
        prompt,
        size=size,
        quality=quality,
        output_format=output_format,
        output_compression=output_compression,
        n=n,
        background=background,
    )

    print(f"🖼️ Editing image via Azure OpenAI ({deployment})")
    print(f"📝 Prompt: {prompt}")
    print(f"🧷 Input images: {len(input_images)}")
    print(f"📐 Size: {size}  Quality: {quality}  Format: {output_format}")
    if mask_path:
        print(f"🎭 Mask: {mask_path}")
        if len(input_images) > 1:
            print("ℹ️ When multiple input images are provided, Azure applies the mask to the first image.")
    if background:
        print(f"🧱 Background: {background}")

    with ExitStack() as stack:
        files = []
        for image_path_str in input_images:
            image_path = Path(image_path_str)
            image_handle = stack.enter_context(open(image_path, "rb"))
            files.append(("image", (image_path.name, image_handle, _guess_mime_type(image_path))))

        if mask_path:
            mask = Path(mask_path)
            mask_handle = stack.enter_context(open(mask, "rb"))
            files.append(("mask", (mask.name, mask_handle, _guess_mime_type(mask))))

        response = requests.post(
            url,
            headers=_build_headers(api_key),
            data=data,
            files=files,
            timeout=120,
        )

    result = _decode_response(response)
    return _save_result_image(
        result,
        output_path=output_path,
        output_format=output_format,
        post_process=post_process,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


class HelpFormatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter):
    """Combine readable examples with default-value help text."""


def _validate_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    if args.mask and not args.input_image:
        parser.error("--mask requires at least one --input-image")
    if args.background == "transparent" and args.format != "png":
        parser.error("--background transparent requires --format png")


def main():
    parser = argparse.ArgumentParser(
        description="Generate or edit images with an Azure OpenAI GPT Image deployment.",
        formatter_class=HelpFormatter,
        epilog="""\
Examples:
  python azure_generate_image.py "A red fox in an autumn forest"
  python azure_generate_image.py "Wide cinematic skyline" --size 2048x1152 --quality auto
  python azure_generate_image.py "Replace the blank sign with a neon cafe logo" --input-image storefront.png --mask sign-mask.png --skip-post-process
  python azure_generate_image.py "Create a premium gift basket using these references" --input-image soap.png --input-image candle.png --input-image towel.png
""",
    )

    parser.add_argument("prompt", help="Text prompt used for image generation or edits")
    parser.add_argument(
        "--input-image",
        "-i",
        action="append",
        default=[],
        metavar="PATH",
        type=_existing_file,
        help="Input image path. Repeat to provide multiple reference images; switches the request to the edits endpoint.",
    )
    parser.add_argument(
        "--mask",
        metavar="PATH",
        type=_existing_file,
        help="Optional mask image for inpainting. Requires at least one --input-image.",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="generated_image.png",
        help="Output file path. The extension is adjusted to match the raw API format when needed.",
    )
    parser.add_argument(
        "--size",
        "-s",
        default=DEFAULT_SIZE,
        type=_parse_size,
        help="Image size as 'auto' or WIDTHxHEIGHT, for example 1536x1024 or 2048x1152.",
    )
    parser.add_argument(
        "--quality",
        "-q",
        default=DEFAULT_QUALITY,
        choices=["low", "medium", "high", "auto"],
        help="Image quality setting.",
    )
    parser.add_argument(
        "--format",
        "-f",
        default=DEFAULT_OUTPUT_FORMAT,
        choices=["png", "jpeg", "webp"],
        help="Raw output format returned by the API.",
    )
    parser.add_argument(
        "--compression",
        type=_parse_compression,
        default=DEFAULT_OUTPUT_COMPRESSION,
        help="Output compression 0-100. Applies to JPEG and WebP API output.",
    )
    parser.add_argument(
        "--background",
        choices=["auto", "opaque", "transparent"],
        help="Optional background mode for supported deployments.",
    )
    parser.add_argument(
        "--skip-post-process",
        action="store_true",
        help="Keep the raw API output instead of resizing/compressing to the blog-cover profile.",
    )
    parser.add_argument(
        "--n",
        type=_parse_image_count,
        default=1,
        help="Number of images to request from Azure OpenAI. The script saves the first image only.",
    )
    parser.add_argument(
        "--deployment",
        "-d",
        default=DEFAULT_DEPLOYMENT,
        help=f"Azure deployment name (default: {DEFAULT_DEPLOYMENT}).",
    )
    parser.add_argument(
        "--api-version",
        default=DEFAULT_API_VERSION,
        help=f"Azure API version (default: {DEFAULT_API_VERSION}).",
    )
    parser.add_argument("--endpoint", help="Azure OpenAI endpoint URL (overrides env)")
    parser.add_argument("--api-key", help="Azure OpenAI API key (overrides env)")

    args = parser.parse_args()
    _validate_args(parser, args)

    common_kwargs = {
        "endpoint": args.endpoint,
        "api_key": args.api_key,
        "deployment": args.deployment,
        "api_version": args.api_version,
        "output_path": args.output,
        "size": args.size,
        "quality": args.quality,
        "output_format": args.format,
        "output_compression": args.compression,
        "n": args.n,
        "background": args.background,
        "post_process": not args.skip_post_process,
    }

    if args.input_image:
        edit_image(
            args.prompt,
            input_images=args.input_image,
            mask_path=args.mask,
            **common_kwargs,
        )
    else:
        generate_image(args.prompt, **common_kwargs)


if __name__ == "__main__":
    main()
