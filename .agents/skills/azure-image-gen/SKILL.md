---
name: azure-image-gen
description: "Generate or edit images using an Azure OpenAI gpt-image-2 deployment. Use when the user asks for Azure-hosted GPT Image generation, inpainting, or reference-image workflows. Supports modern size strings, quality/background controls, and optional blog-friendly post-processing."
---

# Azure OpenAI GPT Image Generation and Editing

Generate or edit images using an Azure OpenAI `gpt-image-2` deployment with optional blog-cover post-processing.

## When to Use This Skill

- User asks to generate an image via **Azure OpenAI**, **gpt-image-2**, or another Azure-hosted GPT Image deployment
- User wants to **edit** an existing image with Azure, including mask-based inpainting
- User wants to create a new image from one or more **reference images** on Azure
- User already has an Azure OpenAI endpoint / deployment and wants to use the Images API directly

**Not for** OpenAI Responses API tool orchestration, OpenRouter image generation, or non-Azure providers. Use the more appropriate skill for those flows.

## Prerequisites

The script needs two environment variables (set them in the shell or in a `.env` file):

| Variable | Example |
|----------|---------|
| `AZURE_OPENAI_ENDPOINT` | `https://<resource>.openai.azure.com` |
| `AZURE_OPENAI_API_KEY` | Your Azure API key |

Python dependencies: `requests`, `Pillow` (for optional post-processing).

```bash
pip install requests Pillow
```

## Quick Start

### Basic generation
```bash
python .agents/skills/azure-image-gen/scripts/azure_generate_image.py "A photograph of a red fox in an autumn forest"
```

### Edit an existing image
```bash
python .agents/skills/azure-image-gen/scripts/azure_generate_image.py \
  "Replace the empty sign with a neon cafe logo" \
  --input-image storefront.png \
  --mask sign-mask.png \
  --skip-post-process
```

### Use multiple reference images
```bash
python .agents/skills/azure-image-gen/scripts/azure_generate_image.py \
  "Create a premium gift basket using these references" \
  --input-image soap.png \
  --input-image candle.png \
  --input-image towel.png \
  --size 2048x1152 \
  --quality auto \
  --skip-post-process
```

## Procedure

1. **Verify credentials**: Confirm `AZURE_OPENAI_ENDPOINT` and `AZURE_OPENAI_API_KEY` are set (env vars or `.env`). If missing, ask the user for them.
2. **Choose the API path**:
   - No `--input-image` flags: generation flow (`/images/generations`)
   - One or more `--input-image` flags: edit/reference-image flow (`/images/edits`)
   - Optional `--mask`: inpainting on the first input image
3. **Build the command**:
   ```bash
   python .agents/skills/azure-image-gen/scripts/azure_generate_image.py "<prompt>" [options]
   ```
4. **Run the script** and note the printed final file path.
5. **Preserve or move the output** as needed. Use `--skip-post-process` when the user wants the raw API output instead of the default blog-cover optimization.

## CLI Reference

```text
python azure_generate_image.py <prompt> [options]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--input-image`, `-i` | none | Input image path. Repeat to provide multiple reference images; switches to the edits endpoint |
| `--mask` | none | Optional inpainting mask. Requires at least one `--input-image` |
| `--output`, `-o` | `generated_image.png` | Output file path. The raw file extension is adjusted to match the API format when needed |
| `--size`, `-s` | `1024x1024` | `auto` or any `WIDTHxHEIGHT` string, such as `1536x1024` or `2048x1152` |
| `--quality`, `-q` | `medium` | `low`, `medium`, `high`, `auto` |
| `--format`, `-f` | `png` | Raw API output format: `png`, `jpeg`, `webp` |
| `--compression` | `100` | 0-100 compression for JPEG / WebP API output |
| `--background` | none | Optional background mode: `auto`, `opaque`, `transparent` |
| `--skip-post-process` | off | Keep the raw API output instead of resizing/compressing it |
| `--n` | `1` | Number of images to request. The script currently saves the first image only |
| `--deployment`, `-d` | `gpt-image-2` | Azure deployment name |
| `--api-version` | `2025-04-01-preview` | Azure API version |
| `--endpoint` | from env | Override `AZURE_OPENAI_ENDPOINT` |
| `--api-key` | from env | Override `AZURE_OPENAI_API_KEY` |

## Usage Examples

### Larger generation with newer size support
```bash
python .agents/skills/azure-image-gen/scripts/azure_generate_image.py "Wide cinematic skyline" --size 2048x1152 --quality auto
```

### Keep raw WebP output
```bash
python .agents/skills/azure-image-gen/scripts/azure_generate_image.py "Minimal product hero" --format webp --compression 70 --skip-post-process
```

### Inpaint an uploaded image
```bash
python .agents/skills/azure-image-gen/scripts/azure_generate_image.py "Replace the pool float with a flamingo" --input-image lounge.png --mask mask.png --skip-post-process
```

### Multi-image reference workflow
```bash
python .agents/skills/azure-image-gen/scripts/azure_generate_image.py "Compose a magazine-worthy flat lay from these references" --input-image watch.png --input-image wallet.png --input-image pen.png --quality high --skip-post-process
```

## Post-Processing

By default, the script keeps the repository's existing blog-cover optimization flow:

1. **Resizes** to a maximum width of **500 px**
2. **Compresses** toward ~200 KB
3. May rewrite the raw API file into a blog-friendly final `.jpg`

Use `--skip-post-process` when the user wants:

- the raw API output format preserved (`png`, `jpeg`, or `webp`)
- higher-resolution results from `gpt-image-2`
- edit/reference-image outputs without automatic cover optimization

## Azure-Specific Notes

- This skill stays on Azure's deployment-based Images API rather than the OpenAI Responses API.
- Repeating `--input-image` sends multiple image parts to Azure's edits endpoint for reference-image workflows.
- If a mask is supplied with multiple input images, treat the **first** input image as the masked base image.
- Keep `--deployment` configurable because Azure deployment names are resource-specific.

## Prompt Guidelines

- Be explicit about the desired style, framing, lighting, and composition.
- For edits, say both **what to preserve** and **what to change**.
- For masked edits, describe the intended replacement rather than only describing the mask geometry.
- Avoid adding prompt or metadata text into the image unless the user explicitly wants visible text rendered.

## Error Handling

- **Missing credentials**: Script prints clear instructions for setting `AZURE_OPENAI_ENDPOINT` / `AZURE_OPENAI_API_KEY`.
- **Missing input files**: CLI validation fails before any network call.
- **API errors**: HTTP status code and response body are surfaced clearly.
- **Missing Pillow**: Warning printed; post-processing skipped and the raw API output is kept.
