---
name: generate-image-azure
description: Generate images with Azure OpenAI image deployments such as gpt-image-1.5. Use when the user wants Azure-hosted image generation instead of OpenRouter, especially when they provide an Azure OpenAI endpoint, deployment, or curl example.
---

# Generate Image with Azure OpenAI

Generate standard-quality images using an Azure OpenAI image deployment, defaulting to `gpt-image-1.5` when the deployment is not explicitly overridden.

## When to Use This Skill

**Use generate-image-azure for:**
- Azure OpenAI image generation requests
- Prompts that include an Azure OpenAI endpoint or deployment URL
- Teams that already store credentials in Azure instead of OpenRouter
- General-purpose image generation for photos, illustrations, concept art, and visual assets

**Use `generate-image` instead for:**
- OpenRouter-based image generation
- OpenRouter image editing workflows
- Cases where the user explicitly wants Gemini or FLUX through OpenRouter

**Use `scientific-schematics` instead for:**
- Flowcharts and process diagrams
- Circuit diagrams and electrical schematics
- Biological pathways and signaling cascades
- System architecture diagrams
- Any technical or schematic diagram

## Quick Start

Use the helper script in this skill:

```bash
# Generate a new image with the default deployment
python .agents/skills/generate-image-azure/scripts/generate_image_azure.py "A photograph of a red fox in an autumn forest"

# Generate a JPEG at a custom path
python .agents/skills/generate-image-azure/scripts/generate_image_azure.py "A watercolor lighthouse on a cliff" --output lighthouse.jpg --output-format jpeg
```

This generates an image and saves it as `generated_image.png` by default.

## API Key and Endpoint Setup

**CRITICAL**: The script requires Azure OpenAI configuration. Before running, check the project's `.env` file or environment variables.

### Minimum required variable
- `AZURE_API_KEY`

### Recommended variables
- `AZURE_OPENAI_IMAGE_URL` — full request URL, for example:
  `https://your-resource.openai.azure.com/openai/deployments/gpt-image-1.5/images/generations?api-version=2024-02-01`
- or, instead of the full URL:
  - `AZURE_OPENAI_ENDPOINT` — base resource URL such as `https://your-resource.openai.azure.com`
  - `AZURE_OPENAI_IMAGE_DEPLOYMENT` — defaults to `gpt-image-1.5`
  - `AZURE_OPENAI_API_VERSION` — defaults to `2024-02-01`

If configuration is missing, add entries like these to `.env`:

```env
AZURE_API_KEY=your-azure-api-key-here
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_IMAGE_DEPLOYMENT=gpt-image-1.5
AZURE_OPENAI_API_VERSION=2024-02-01
```

The script automatically searches for a `.env` file in the current directory and parent directories.

## Default Request Settings

These defaults mirror the Azure curl pattern the user provided:

- Deployment: `gpt-image-1.5`
- Size: `1024x1024`
- Quality: `medium`
- Output format: `png`
- Output compression: `100`
- Count: `1`

Only override these when the user explicitly asks.

## Common Usage Patterns

### Basic generation
```bash
python .agents/skills/generate-image-azure/scripts/generate_image_azure.py "A photograph of a red fox in an autumn forest"
```

### Custom size
```bash
python .agents/skills/generate-image-azure/scripts/generate_image_azure.py "A cinematic desert landscape at sunset" --size 1536x1024
```

### Higher or lower quality
```bash
python .agents/skills/generate-image-azure/scripts/generate_image_azure.py "A hand-drawn fantasy map" --quality high
```

### Custom output path and format
```bash
python .agents/skills/generate-image-azure/scripts/generate_image_azure.py "A neon cyberpunk alley in the rain" --output alley.webp --output-format webp
```

### Override deployment explicitly
```bash
python .agents/skills/generate-image-azure/scripts/generate_image_azure.py "A product hero shot of a ceramic mug" --deployment gpt-image-1.5
```

### Use a full endpoint URL explicitly
```bash
python .agents/skills/generate-image-azure/scripts/generate_image_azure.py "A studio portrait of a golden retriever" --endpoint-url "https://your-resource.openai.azure.com/openai/deployments/gpt-image-1.5/images/generations?api-version=2024-02-01"
```

## Script Parameters

- `prompt` (required): Text description of the image to generate
- `--output` or `-o`: Output file path (default: `generated_image.png`)
- `--endpoint-url`: Full Azure OpenAI image generation URL
- `--endpoint`: Azure OpenAI resource endpoint without the path
- `--deployment` or `-d`: Deployment name (default: `gpt-image-1.5`)
- `--api-version`: Azure API version (default: `2024-02-01`)
- `--size`: Image size (default: `1024x1024`)
- `--quality`: Quality level (default: `medium`)
- `--output-format`: Output format sent to Azure (default: `png`)
- `--output-compression`: Compression sent to Azure (default: `100`)
- `--count` or `-n`: Number of images to request (default: `1`)
- `--api-key`: Azure API key override
- `--skip-post-process`: Skip local resize/compression after generation

## Image Post-Processing

After generation, the script automatically:
1. **Resizes** the image to a maximum width of **500px** while preserving aspect ratio.
2. **Compresses** the file if it exceeds **500KB**.

This keeps output lightweight and suitable for blog usage. If `Pillow` is not installed, the script prints a warning and skips post-processing.

## Error Handling

The script provides clear error messages for:
- Missing API key or endpoint configuration
- HTTP errors returned by Azure OpenAI
- Missing dependencies such as `requests`
- Unexpected response payloads
- Invalid or missing base64 image data

If the request fails, inspect the returned Azure error message before retrying.

## Critical Prompt Requirements

**IMPORTANT: No Meta Instructions in Output**

When generating prompts for Azure image models, ensure the generated image does NOT contain visible text showing:
- The prompt or instructions used to create it
- System instructions or metadata
- Watermarks or AI-generation labels
- Layout descriptions
- Font or color-specification text

Always include this instruction in prompts when helpful: "Do not include any text showing the prompt, instructions, layout descriptions, font/color specifications, or metadata in the generated image."

## Notes

- This skill is focused on **image generation** rather than editing.
- The script sends both `Authorization: Bearer` and `api-key` headers for better Azure compatibility.
- Azure responses are expected to include `data[0].b64_json`; if the format differs, inspect the raw response.
- Generation time varies by deployment and image size.
- Default to standard-quality output unless the user explicitly requests higher quality.

## Integration with Other Skills

- **generate-image**: Use for OpenRouter-based generation or editing workflows
- **scientific-schematics**: Use for technical diagrams and process visuals
- **create-blog-post-from-url**: Pair with this skill when a blog post needs an Azure-generated hero image
