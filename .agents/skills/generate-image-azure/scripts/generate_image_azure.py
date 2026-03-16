#!/usr/bin/env python3
"""
Generate images using Azure OpenAI image deployments.

Defaults are aligned with a common Azure curl pattern:
- deployment: gpt-image-1.5
- api-version: 2024-02-01
- size: 1024x1024
- quality: medium
- output_format: png
- output_compression: 100
- n: 1
"""

import argparse
import base64
import json
import sys
from pathlib import Path
from typing import Optional


MAX_WIDTH = 500
MAX_FILE_SIZE_KB = 220
DEFAULT_DEPLOYMENT = "gpt-image-1.5"
DEFAULT_API_VERSION = "2024-02-01"
DEFAULT_SIZE = "1024x1024"
DEFAULT_QUALITY = "medium"
DEFAULT_OUTPUT_FORMAT = "png"
DEFAULT_OUTPUT_COMPRESSION = 100
DEFAULT_COUNT = 1


def _load_env_value_from_file(key: str) -> Optional[str]:
    current_dir = Path.cwd()
    for parent in [current_dir] + list(current_dir.parents):
        env_file = parent / ".env"
        if not env_file.exists():
            continue

        with open(env_file, "r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                env_key, env_value = line.split("=", 1)
                if env_key.strip() == key:
                    return env_value.strip().strip('"').strip("'")

    return None


def get_config_value(cli_value: Optional[str], env_key: str) -> Optional[str]:
    if cli_value:
        return cli_value
    return _load_env_value_from_file(env_key)


def build_endpoint_url(
    endpoint_url: Optional[str],
    endpoint: Optional[str],
    deployment: str,
    api_version: str,
) -> Optional[str]:
    if endpoint_url:
        return endpoint_url

    if not endpoint:
        return None

    return (
        endpoint.rstrip("/")
        + f"/openai/deployments/{deployment}/images/generations"
        + f"?api-version={api_version}"
    )


def save_base64_image(base64_data: str, output_path: str) -> None:
    image_data = base64.b64decode(base64_data)
    with open(output_path, "wb") as handle:
        handle.write(image_data)


def resize_and_compress_image(output_path: str) -> str:
    try:
        from PIL import Image
        import io
    except ImportError:
        print("⚠️  Pillow not installed; skipping resize/compress. Install with: pip install Pillow")
        return output_path

    path = Path(output_path)
    img = Image.open(path)

    if img.width > MAX_WIDTH:
        ratio = MAX_WIDTH / img.width
        new_height = int(img.height * ratio)
        img = img.resize((MAX_WIDTH, new_height), Image.LANCZOS)
        print(f"📐 Resized to {MAX_WIDTH}x{new_height}")

    ext = path.suffix.lower()
    is_png = ext == ".png"

    img.save(output_path, optimize=True)
    file_size_kb = path.stat().st_size / 1024

    if file_size_kb <= MAX_FILE_SIZE_KB:
        print(f"📦 File size: {file_size_kb:.1f}KB")
        return output_path

    jpeg_path = str(path.with_suffix(".jpg"))
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    quality = 85
    size_kb = file_size_kb
    buf = None

    while quality >= 40:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        size_kb = len(buf.getvalue()) / 1024
        if size_kb <= MAX_FILE_SIZE_KB:
            break
        quality -= 10

    if buf is None:
        return output_path

    with open(jpeg_path, "wb") as handle:
        handle.write(buf.getvalue())
    print(f"🗜️  Compressed to JPEG (quality={quality}): {size_kb:.1f}KB → {jpeg_path}")

    if is_png and jpeg_path != output_path:
        path.unlink()

    return jpeg_path


def generate_image(
    prompt: str,
    output_path: str = "generated_image.png",
    endpoint_url: Optional[str] = None,
    endpoint: Optional[str] = None,
    deployment: str = DEFAULT_DEPLOYMENT,
    api_version: str = DEFAULT_API_VERSION,
    size: str = DEFAULT_SIZE,
    quality: str = DEFAULT_QUALITY,
    output_format: str = DEFAULT_OUTPUT_FORMAT,
    output_compression: int = DEFAULT_OUTPUT_COMPRESSION,
    count: int = DEFAULT_COUNT,
    api_key: Optional[str] = None,
    skip_post_process: bool = False,
) -> dict:
    try:
        import requests
    except ImportError:
        print("❌ Error: 'requests' library not found. Install with: pip install requests")
        sys.exit(1)

    resolved_api_key = get_config_value(api_key, "AZURE_API_KEY")
    resolved_endpoint_url = get_config_value(endpoint_url, "AZURE_OPENAI_IMAGE_URL")
    resolved_endpoint = get_config_value(endpoint, "AZURE_OPENAI_ENDPOINT")
    resolved_deployment = get_config_value(deployment, "AZURE_OPENAI_IMAGE_DEPLOYMENT") or DEFAULT_DEPLOYMENT
    resolved_api_version = get_config_value(api_version, "AZURE_OPENAI_API_VERSION") or DEFAULT_API_VERSION

    url = build_endpoint_url(
        endpoint_url=resolved_endpoint_url,
        endpoint=resolved_endpoint,
        deployment=resolved_deployment,
        api_version=resolved_api_version,
    )

    if not resolved_api_key:
        print("❌ Error: AZURE_API_KEY not found!")
        print("\nAdd it to your .env file or pass --api-key.")
        print("Example:")
        print("AZURE_API_KEY=your-azure-api-key-here")
        sys.exit(1)

    if not url:
        print("❌ Error: Azure endpoint configuration not found!")
        print("\nProvide one of the following:")
        print("- AZURE_OPENAI_IMAGE_URL in .env")
        print("- or AZURE_OPENAI_ENDPOINT plus optional deployment/api version")
        print("- or pass --endpoint-url / --endpoint on the command line")
        sys.exit(1)

    print(f"🎨 Generating image with Azure deployment: {resolved_deployment}")
    print(f"📝 Prompt: {prompt}")
    print(f"🔗 Endpoint: {url}")

    response = requests.post(
        url=url,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {resolved_api_key}",
            "api-key": resolved_api_key,
        },
        json={
            "prompt": prompt,
            "size": size,
            "quality": quality,
            "output_compression": output_compression,
            "output_format": output_format,
            "n": count,
        },
        timeout=120,
    )

    if response.status_code != 200:
        print(f"❌ API Error ({response.status_code}): {response.text}")
        sys.exit(1)

    result = response.json()

    images = result.get("data") or []
    if not images:
        print("❌ No image data found in response")
        print(json.dumps(result, indent=2))
        sys.exit(1)

    first_image = images[0]
    base64_data = first_image.get("b64_json")
    if not base64_data:
        print("❌ Response did not contain data[0].b64_json")
        print(json.dumps(result, indent=2))
        sys.exit(1)

    save_base64_image(base64_data, output_path)

    final_output_path = output_path
    if not skip_post_process:
        final_output_path = resize_and_compress_image(output_path)

    print(f"✅ Image saved to: {final_output_path}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate images using Azure OpenAI image deployments",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate with .env configuration
  python generate_image_azure.py "A photograph of a red fox in an autumn forest"

  # Provide the full Azure image URL directly
  python generate_image_azure.py "A product shot of a fountain pen" --endpoint-url "https://your-resource.openai.azure.com/openai/deployments/gpt-image-1.5/images/generations?api-version=2024-02-01"

  # Override size and quality
  python generate_image_azure.py "A watercolor lighthouse" --size 1536x1024 --quality high --output lighthouse.png
        """,
    )

    parser.add_argument("prompt", type=str, help="Text description of the image to generate")
    parser.add_argument("--output", "-o", type=str, default="generated_image.png", help="Output file path")
    parser.add_argument("--endpoint-url", type=str, help="Full Azure OpenAI image generation URL")
    parser.add_argument("--endpoint", type=str, help="Azure OpenAI endpoint base URL")
    parser.add_argument("--deployment", "-d", type=str, default=DEFAULT_DEPLOYMENT, help=f"Deployment name (default: {DEFAULT_DEPLOYMENT})")
    parser.add_argument("--api-version", type=str, default=DEFAULT_API_VERSION, help=f"Azure API version (default: {DEFAULT_API_VERSION})")
    parser.add_argument("--size", type=str, default=DEFAULT_SIZE, help=f"Image size (default: {DEFAULT_SIZE})")
    parser.add_argument("--quality", type=str, default=DEFAULT_QUALITY, help=f"Quality (default: {DEFAULT_QUALITY})")
    parser.add_argument("--output-format", type=str, default=DEFAULT_OUTPUT_FORMAT, help=f"Output format sent to Azure (default: {DEFAULT_OUTPUT_FORMAT})")
    parser.add_argument("--output-compression", type=int, default=DEFAULT_OUTPUT_COMPRESSION, help=f"Output compression sent to Azure (default: {DEFAULT_OUTPUT_COMPRESSION})")
    parser.add_argument("--count", "-n", type=int, default=DEFAULT_COUNT, help=f"Number of images to request (default: {DEFAULT_COUNT})")
    parser.add_argument("--api-key", type=str, help="Azure API key override")
    parser.add_argument("--skip-post-process", action="store_true", help="Skip local resize/compression")

    args = parser.parse_args()

    generate_image(
        prompt=args.prompt,
        output_path=args.output,
        endpoint_url=args.endpoint_url,
        endpoint=args.endpoint,
        deployment=args.deployment,
        api_version=args.api_version,
        size=args.size,
        quality=args.quality,
        output_format=args.output_format,
        output_compression=args.output_compression,
        count=args.count,
        api_key=args.api_key,
        skip_post_process=args.skip_post_process,
    )


if __name__ == "__main__":
    main()
