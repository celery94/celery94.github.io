---
name: azure-image-gen
description: "Generate images using Azure OpenAI gpt-image-1.5 deployment. Use when the user asks to create, generate, or produce images via Azure OpenAI, gpt-image-1.5, or an Azure-hosted image model. Supports size, quality, and format options with automatic blog-friendly post-processing."
---

# Azure OpenAI Image Generation

Generate images using the Azure OpenAI `gpt-image-1.5` deployment with automatic blog-cover post-processing.

## When to Use This Skill

- User asks to generate an image via **Azure OpenAI** or **gpt-image-1.5**
- User specifies Azure-based image generation (as opposed to OpenRouter / Gemini)
- User provides an Azure OpenAI endpoint and wants to use the Images API

**Not for editing existing images** — this skill is generation-only. For image editing or OpenRouter-based generation, use the `generate-image` skill instead.

## Prerequisites

The script needs two environment variables (set them in the shell or in a `.env` file):

| Variable | Example |
|----------|---------|
| `AZURE_OPENAI_ENDPOINT` | `https://<resource>.openai.azure.com` |
| `AZURE_OPENAI_API_KEY` | Your Azure API key |

Python dependencies: `requests`, `Pillow` (for post-processing).

```bash
pip install requests Pillow
```

## Quick Start

```bash
python .agents/skills/azure-image-gen/scripts/azure_generate_image.py "A photograph of a red fox in an autumn forest"
```

## Procedure

1. **Verify credentials**: Confirm `AZURE_OPENAI_ENDPOINT` and `AZURE_OPENAI_API_KEY` are set (env vars or `.env`). If missing, ask the user for them.
2. **Build the command**: Construct the CLI invocation with the user's prompt and desired options.
3. **Run the script**:
   ```bash
   python .agents/skills/azure-image-gen/scripts/azure_generate_image.py "<prompt>" [options]
   ```
4. **Check output**: The script prints the final file path after post-processing. Verify the file exists and size is reasonable.
5. **Move/rename** the output if the user specified a target path or needs it in a particular asset directory.

## CLI Reference

```
python azure_generate_image.py <prompt> [options]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--output`, `-o` | `generated_image.png` | Output file path |
| `--size`, `-s` | `1024x1024` | `1024x1024`, `1024x1536`, `1536x1024`, `1792x1024`, `1024x1792` |
| `--quality`, `-q` | `medium` | `low`, `medium`, `high` |
| `--format`, `-f` | `png` | API output format: `png`, `jpeg`, `webp` |
| `--compression` | `100` | 0–100 (100 = lossless) |
| `--n` | `1` | Number of images to generate |
| `--deployment`, `-d` | `gpt-image-1.5` | Azure deployment name |
| `--api-version` | `2024-02-01` | Azure API version |
| `--endpoint` | from env | Override `AZURE_OPENAI_ENDPOINT` |
| `--api-key` | from env | Override `AZURE_OPENAI_API_KEY` |

## Usage Examples

### Basic generation
```bash
python .agents/skills/azure-image-gen/scripts/azure_generate_image.py "A sunset over mountains"
```

### Custom size and quality
```bash
python .agents/skills/azure-image-gen/scripts/azure_generate_image.py "Abstract art" --size 1792x1024 --quality high
```

### Custom output path
```bash
python .agents/skills/azure-image-gen/scripts/azure_generate_image.py "Company logo" --output src/assets/logo.png
```

### Lower compression for smaller file
```bash
python .agents/skills/azure-image-gen/scripts/azure_generate_image.py "Banner image" --format png --compression 80
```

## Post-Processing

After generation, the script automatically:
1. **Resizes** to a maximum width of **500 px** (aspect ratio preserved).
2. **Chooses WebP or JPEG** based on image complexity analysis.
3. **Compresses** toward ~200 KB for blog-friendly file sizes.

The final output may be a `.webp` or `.jpg` file. The `Pillow` library is required for this step; without it, the raw API output is kept as-is.

## Prompt Guidelines

- Be specific and descriptive for best results.
- **Do not** include meta-instructions like "layout: left panel" in the prompt.
- Always append: *"Do not include any text showing the prompt, instructions, or metadata in the generated image."*

## Error Handling

- **Missing credentials**: Script prints clear instructions for setting `AZURE_OPENAI_ENDPOINT` / `AZURE_OPENAI_API_KEY`.
- **API errors**: HTTP status code and response body are printed.
- **Missing Pillow**: Warning printed; post-processing skipped, raw image preserved.
