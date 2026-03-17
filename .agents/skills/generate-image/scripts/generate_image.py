#!/usr/bin/env python3
"""
Generate and edit images using OpenRouter API with various image generation models.

Supports models like:
- google/gemini-3.1-flash-image-preview (default; generation and editing)
- black-forest-labs/flux.2-pro (generation and editing)
- black-forest-labs/flux.2-flex (generation)
- And more image generation models available on OpenRouter

For image editing, provide an input image along with an editing prompt.
"""

import sys
import json
import base64
import argparse
import io
from pathlib import Path
from typing import Optional


def check_env_file() -> Optional[str]:
    """Check if .env file exists and contains OPENROUTER_API_KEY."""
    # Look for .env in current directory and parent directories
    current_dir = Path.cwd()
    for parent in [current_dir] + list(current_dir.parents):
        env_file = parent / ".env"
        if env_file.exists():
            with open(env_file, 'r') as f:
                for line in f:
                    if line.startswith('OPENROUTER_API_KEY='):
                        api_key = line.split('=', 1)[1].strip().strip('"').strip("'")
                        if api_key:
                            return api_key
    return None


def load_image_as_base64(image_path: str) -> str:
    """Load an image file and return it as a base64 data URL."""
    path = Path(image_path)
    if not path.exists():
        print(f"❌ Error: Image file not found: {image_path}")
        sys.exit(1)
    
    # Determine MIME type from extension
    ext = path.suffix.lower()
    mime_types = {
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
    }
    mime_type = mime_types.get(ext, 'image/png')
    
    with open(path, 'rb') as f:
        image_data = f.read()
    
    base64_data = base64.b64encode(image_data).decode('utf-8')
    return f"data:{mime_type};base64,{base64_data}"


def save_base64_image(base64_data: str, output_path: str) -> None:
    """Save base64 encoded image to file."""
    # Remove data URL prefix if present
    if ',' in base64_data:
        base64_data = base64_data.split(',', 1)[1]

    # Decode and save
    image_data = base64.b64decode(base64_data)
    with open(output_path, 'wb') as f:
        f.write(image_data)


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
    """
    Resize image to max 500px width and compress toward ~200KB for lightweight cover images.
    Automatically chooses WebP or JPEG based on image complexity, with format-size fallback.
    Returns the final output path (may change extension to .webp or .jpg).
    """
    try:
        from PIL import Image, ImageFilter, ImageStat
    except ImportError:
        print("⚠️  Pillow not installed; skipping resize/compress. Install with: pip install Pillow")
        return output_path

    def detect_transparency(image):
        if 'A' not in image.getbands():
            return False
        alpha_extrema = image.getchannel('A').getextrema()
        return alpha_extrema[0] < 255

    def analyze_image_complexity(image):
        sample = image.convert('RGB')
        sample.thumbnail((256, 256), Image.LANCZOS)

        grayscale = sample.convert('L')
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

        return {
            "score": complexity,
            "contrast": contrast,
            "edge_mean": edge_mean,
        }

    def choose_preferred_format(image, metrics):
        if detect_transparency(image):
            return 'WEBP', 'transparency detected'

        if metrics['score'] <= COMPLEXITY_WEBP_THRESHOLD:
            return 'WEBP', f"lower complexity score ({metrics['score']:.2f})"

        return 'JPEG', f"higher complexity score ({metrics['score']:.2f})"

    def encode_candidate(image, fmt, quality):
        candidate = image
        buf = io.BytesIO()

        if fmt == 'JPEG':
            if candidate.mode not in ('RGB', 'L'):
                candidate = candidate.convert('RGB')
            candidate.save(
                buf,
                format='JPEG',
                quality=quality,
                optimize=True,
                progressive=True,
            )
        elif fmt == 'WEBP':
            if candidate.mode not in ('RGB', 'RGBA', 'L'):
                candidate = candidate.convert('RGBA' if detect_transparency(candidate) else 'RGB')
            candidate.save(
                buf,
                format='WEBP',
                quality=quality,
                method=6,
            )
        else:
            raise ValueError(f"Unsupported format: {fmt}")

        data = buf.getvalue()
        return data, len(data) / 1024

    def build_best_variant(image, fmt):
        min_quality = MIN_WEBP_QUALITY if fmt == 'WEBP' else MIN_JPEG_QUALITY
        start_quality = 90 if fmt == 'WEBP' else 85
        working_img = image
        best_variant = None

        while True:
            quality = start_quality

            while quality >= min_quality:
                candidate_data, candidate_size_kb = encode_candidate(working_img, fmt, quality)
                candidate = {
                    'format': fmt,
                    'data': candidate_data,
                    'size_kb': candidate_size_kb,
                    'quality': quality,
                    'width': working_img.width,
                    'height': working_img.height,
                }

                if best_variant is None or candidate_size_kb < best_variant['size_kb']:
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
                f"🪶 Reducing dimensions further to {next_width}x{next_height} "
                f"while testing {fmt} to approach {TARGET_FILE_SIZE_KB}KB"
            )

    path = Path(output_path)
    img = Image.open(path)

    # Resize if wider than MAX_WIDTH
    if img.width > MAX_WIDTH:
        ratio = MAX_WIDTH / img.width
        new_height = int(img.height * ratio)
        img = img.resize((MAX_WIDTH, new_height), Image.LANCZOS)
        print(f"📐 Resized to {MAX_WIDTH}x{new_height}")

    # Keep a locally optimized copy if it already fits the blog-cover target.
    img.save(output_path, optimize=True)
    file_size_kb = path.stat().st_size / 1024

    if file_size_kb <= MAX_FILE_SIZE_KB:
        print(f"📦 File size: {file_size_kb:.1f}KB")
        return output_path

    metrics = analyze_image_complexity(img)
    preferred_format, reason = choose_preferred_format(img, metrics)
    alternate_format = 'JPEG' if preferred_format == 'WEBP' else 'WEBP'
    print(
        f"🧠 Preferred cover format: {preferred_format} "
        f"({reason}; edge mean {metrics['edge_mean']:.1f}, contrast {metrics['contrast']:.1f})"
    )

    preferred_variant = build_best_variant(img, preferred_format)
    alternate_variant = build_best_variant(img, alternate_format)

    chosen_variant = preferred_variant
    if alternate_variant is not None:
        preferred_over_limit = preferred_variant['size_kb'] > MAX_FILE_SIZE_KB
        alternate_hits_target = alternate_variant['size_kb'] <= MAX_FILE_SIZE_KB
        alternate_meaningfully_smaller = alternate_variant['size_kb'] + 15 < preferred_variant['size_kb']

        if (preferred_over_limit and alternate_hits_target) or alternate_meaningfully_smaller:
            chosen_variant = alternate_variant
            print(
                f"🔁 Switching to {alternate_variant['format']} because it produced a smaller cover file "
                f"({alternate_variant['size_kb']:.1f}KB vs {preferred_variant['size_kb']:.1f}KB)"
            )

    extension = '.webp' if chosen_variant['format'] == 'WEBP' else '.jpg'
    final_path = str(path.with_suffix(extension))

    with open(final_path, 'wb') as f:
        f.write(chosen_variant['data'])

    print(
        f"🗜️  Saved cover as {chosen_variant['format']} "
        f"(quality={chosen_variant['quality']}, {chosen_variant['width']}x{chosen_variant['height']}): "
        f"{chosen_variant['size_kb']:.1f}KB → {final_path}"
    )

    if chosen_variant['size_kb'] > MAX_FILE_SIZE_KB:
        print(
            f"⚠️  Final size is still above the ~{TARGET_FILE_SIZE_KB}KB target: "
            f"{chosen_variant['size_kb']:.1f}KB"
        )

    if path.exists() and final_path != output_path:
        path.unlink()

    return final_path


DEFAULT_MODEL = "google/gemini-3.1-flash-image-preview"


def generate_image(
    prompt: str,
    model: str = DEFAULT_MODEL,
    output_path: str = "generated_image.png",
    api_key: Optional[str] = None,
    input_image: Optional[str] = None
) -> dict:
    """
    Generate or edit an image using OpenRouter API.

    Args:
        prompt: Text description of the image to generate, or editing instructions
        model: OpenRouter model ID (default: google/gemini-3.1-flash-image-preview)
        output_path: Path to save the generated image
        api_key: OpenRouter API key (will check .env if not provided)
        input_image: Path to an input image for editing (optional)

    Returns:
        dict: Response from OpenRouter API
    """
    try:
        import requests
    except ImportError:
        print("Error: 'requests' library not found. Install with: pip install requests")
        sys.exit(1)

    # Check for API key
    if not api_key:
        api_key = check_env_file()

    if not api_key:
        print("❌ Error: OPENROUTER_API_KEY not found!")
        print("\nPlease create a .env file in your project directory with:")
        print("OPENROUTER_API_KEY=your-api-key-here")
        print("\nOr set the environment variable:")
        print("export OPENROUTER_API_KEY=your-api-key-here")
        print("\nGet your API key from: https://openrouter.ai/keys")
        sys.exit(1)

    # Determine if this is generation or editing
    is_editing = input_image is not None
    
    if is_editing:
        print(f"✏️ Editing image with model: {model}")
        print(f"📷 Input image: {input_image}")
        print(f"📝 Edit prompt: {prompt}")
        
        # Load input image as base64
        image_data_url = load_image_as_base64(input_image)
        
        # Build multimodal message content for image editing
        message_content = [
            {
                "type": "text",
                "text": prompt
            },
            {
                "type": "image_url",
                "image_url": {
                    "url": image_data_url
                }
            }
        ]
    else:
        print(f"🎨 Generating image with model: {model}")
        print(f"📝 Prompt: {prompt}")
        message_content = prompt

    # Make API request
    response = requests.post(
        url="https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": message_content
                }
            ],
            "modalities": ["image", "text"]
        }
    )

    # Check for errors
    if response.status_code != 200:
        print(f"❌ API Error ({response.status_code}): {response.text}")
        sys.exit(1)

    result = response.json()

    # Extract and save image
    if result.get("choices"):
        message = result["choices"][0]["message"]

        # Handle both 'images' and 'content' response formats
        images = []

        if message.get("images"):
            images = message["images"]
        elif message.get("content"):
            # Some models return content as array with image parts
            content = message["content"]
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "image":
                        images.append(part)

        if images:
            # Save the first image
            image = images[0]
            if "image_url" in image:
                image_url = image["image_url"]["url"]
                save_base64_image(image_url, output_path)
                output_path = resize_and_compress_image(output_path)
                print(f"✅ Image saved to: {output_path}")
            elif "url" in image:
                save_base64_image(image["url"], output_path)
                output_path = resize_and_compress_image(output_path)
                print(f"✅ Image saved to: {output_path}")
            else:
                print(f"⚠️ Unexpected image format: {image}")
        else:
            print("⚠️ No image found in response")
            if message.get("content"):
                print(f"Response content: {message['content']}")
    else:
        print("❌ No choices in response")
        print(f"Response: {json.dumps(result, indent=2)}")

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Generate or edit images using OpenRouter API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate with default model (google/gemini-3.1-flash-image-preview)
  python generate_image.py "A beautiful sunset over mountains"

  # Use a specific model
  python generate_image.py "A cat in space" --model "black-forest-labs/flux.2-pro"

  # Specify output path
  python generate_image.py "Abstract art" --output my_image.png

  # Edit an existing image
  python generate_image.py "Make the sky purple" --input photo.jpg --output edited.png

  # Edit with a specific model
  python generate_image.py "Add a hat to the person" --input portrait.png -m "black-forest-labs/flux.2-pro"

Popular image models:
  - google/gemini-3.1-flash-image-preview (default, normal quality, generation + editing)
  - black-forest-labs/flux.2-pro (alternative, generation + editing)
  - black-forest-labs/flux.2-flex (development version)
        """
    )

    parser.add_argument(
        "prompt",
        type=str,
        help="Text description of the image to generate, or editing instructions"
    )

    parser.add_argument(
        "--model", "-m",
        type=str,
        default=DEFAULT_MODEL,
        help=f"OpenRouter model ID (default: {DEFAULT_MODEL})"
    )

    parser.add_argument(
        "--output", "-o",
        type=str,
        default="generated_image.png",
        help="Output file path (default: generated_image.png)"
    )

    parser.add_argument(
        "--input", "-i",
        type=str,
        help="Input image path for editing (enables edit mode)"
    )

    parser.add_argument(
        "--api-key",
        type=str,
        help="OpenRouter API key (will check .env if not provided)"
    )

    args = parser.parse_args()

    generate_image(
        prompt=args.prompt,
        model=args.model,
        output_path=args.output,
        api_key=args.api_key,
        input_image=args.input
    )


if __name__ == "__main__":
    main()
