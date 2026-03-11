---
name: generate-image
description: Generate or edit images using AI models (FLUX, Gemini). Use for general-purpose image generation including photos, illustrations, artwork, visual assets, concept art, and any image that isn't a technical diagram or schematic. For flowcharts, circuits, pathways, and technical diagrams, use the scientific-schematics skill instead.
---

# Generate Image

Generate high-quality images with `curl` via OpenRouter. Default to `google/gemini-3.1-flash-image-preview` unless the user explicitly asks for another model.

Prefer a **script-first workflow**: when the skill is used inside a writable workspace, create ready-to-run script files and request payload files before executing the API call. Treat inline `curl` snippets as a fallback for explanation-only requests.

## When to Use This Skill

**Use generate-image for:**
- Photos and photorealistic images
- Artistic illustrations and artwork
- Concept art and visual concepts
- Visual assets for presentations or documents
- Image editing and modifications
- Any general-purpose image generation needs

**Use scientific-schematics instead for:**
- Flowcharts and process diagrams
- Circuit diagrams and electrical schematics
- Biological pathways and signaling cascades
- System architecture diagrams
- CONSORT diagrams and methodology flowcharts
- Any technical/schematic diagrams

## Quick Start

Use `curl` to call OpenRouter's Chat Completions API with image output enabled.

## Preferred Execution Workflow

When the user wants the image to actually be generated, do this by default:

1. Create a small working folder for the task, preferably an existing `scripts/`, `tools/`, or temporary workspace folder. If none exists, create something like `tmp/generate-image/`.
2. Save the request body as a JSON file such as `request.json`.
3. Save a ready-to-run script for the current OS:
   - Windows: `generate-image.ps1`
   - macOS/Linux: `generate-image.sh`
4. Save the raw API response to a file such as `response.json`.
5. If needed, add a second helper script to extract base64 image data into a PNG/WebP file.

Default file set:

- `tmp/generate-image/request.json` - OpenRouter request payload
- `tmp/generate-image/generate-image.ps1` - Windows PowerShell runner
- `tmp/generate-image/generate-image.sh` - macOS/Linux runner when relevant
- `tmp/generate-image/response.json` - raw API response

Only skip file creation when:

- the user explicitly asks for a code snippet only;
- the workspace is read-only; or
- the user asks for a one-off command instead of reusable files.

On Windows, prefer creating and using a PowerShell script instead of pasting a long inline command.

```bash
# macOS/Linux
curl https://openrouter.ai/api/v1/chat/completions \
   -H "Content-Type: application/json" \
   -H "Authorization: Bearer $OPENROUTER_API_KEY" \
   -d '{
      "model": "google/gemini-3.1-flash-image-preview",
      "messages": [
         {
            "role": "user",
            "content": "Generate a beautiful sunset over mountains. Do not include any visible prompt text, layout notes, metadata, or watermarks in the image."
         }
      ],
      "modalities": ["image", "text"]
   }'
```

On Windows PowerShell, prefer `curl.exe` to avoid PowerShell alias surprises:

```powershell
curl.exe https://openrouter.ai/api/v1/chat/completions `
   -H "Content-Type: application/json" `
   -H "Authorization: Bearer $env:OPENROUTER_API_KEY" `
   -d '{
      "model": "google/gemini-3.1-flash-image-preview",
      "messages": [
         {
            "role": "user",
            "content": "Generate a beautiful sunset over mountains. Do not include any visible prompt text, layout notes, metadata, or watermarks in the image."
         }
      ],
      "modalities": ["image", "text"]
   }'
```

Use this skill whenever the task is primarily “generate an image” or “edit an image,” and execute the request with `curl` unless the user explicitly asks for a different tool or SDK.

When performing the task for the user, prefer creating the reusable files first, then run the script from the workspace and summarize where the files were written.

## Script Templates

Use these as the default structure when creating ready-made files.

### `request.json`

```json
{
   "model": "google/gemini-3.1-flash-image-preview",
   "messages": [
      {
         "role": "user",
         "content": "Describe the requested image here. Do not include any text showing the prompt, instructions, layout descriptions, font/color specifications, or metadata in the generated image."
      }
   ],
   "modalities": ["image", "text"]
}
```

### `generate-image.ps1`

```powershell
param(
      [string]$RequestFile = ".\\request.json",
      [string]$ResponseFile = ".\\response.json"
)

if (-not $env:OPENROUTER_API_KEY) {
      throw "OPENROUTER_API_KEY is not set. Add it to your .env or current shell session."
}

$body = Get-Content -Raw -Path $RequestFile

curl.exe https://openrouter.ai/api/v1/chat/completions `
    -H "Content-Type: application/json" `
    -H "Authorization: Bearer $env:OPENROUTER_API_KEY" `
    -d $body `
    | Out-File -FilePath $ResponseFile -Encoding utf8

Write-Host "Saved response to $ResponseFile"
```

### `generate-image.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

REQUEST_FILE="${1:-./request.json}"
RESPONSE_FILE="${2:-./response.json}"

if [[ -z "${OPENROUTER_API_KEY:-}" ]]; then
   echo "OPENROUTER_API_KEY is not set. Add it to your .env or current shell session." >&2
   exit 1
fi

curl https://openrouter.ai/api/v1/chat/completions \
   -H "Content-Type: application/json" \
   -H "Authorization: Bearer $OPENROUTER_API_KEY" \
   -d @"$REQUEST_FILE" \
   > "$RESPONSE_FILE"

echo "Saved response to $RESPONSE_FILE"
```

Adjust file names and prompt content as needed, but keep the same overall pattern.

## API Key Setup

**CRITICAL**: The request requires an OpenRouter API key. Before running, check if the user has configured their API key:

1. Look for a `.env` file in the project directory or parent directories
2. Check for `OPENROUTER_API_KEY=<key>` in the `.env` file
3. If not found, inform the user they need to:
   - Create a `.env` file with `OPENROUTER_API_KEY=your-api-key-here`
   - Or set the environment variable for their shell session
   - Get an API key from: https://openrouter.ai/keys

If the workspace does not already contain a `.env` file and the task requires execution, proactively create one with a placeholder entry:

```env
OPENROUTER_API_KEY=your-api-key-here
```

Never put the real API key into generated scripts or checked-in files.

Shell examples:

```bash
export OPENROUTER_API_KEY=your-api-key-here
```

```powershell
$env:OPENROUTER_API_KEY = "your-api-key-here"
```

Never print or log the real API key back to the user.

## Model Selection

**Default model**: `google/gemini-3.1-flash-image-preview` (high quality, recommended)

**Recommended alternatives**:
- `google/gemini-3.1-flash-image-preview` - High quality, supports generation + editing
- `black-forest-labs/flux.2-pro` - Fast, high quality, supports generation + editing
- `black-forest-labs/flux.2-flex` - Fast and cheap, but not as high quality as pro

Select based on:
- **Quality**: Use `google/gemini-3.1-flash-image-preview` by default
- **Editing**: Use Gemini preview or `black-forest-labs/flux.2-pro`
- **Cost**: Use flux.2-flex for generation only

## Common Usage Patterns

### Basic generation
```bash
curl https://openrouter.ai/api/v1/chat/completions \
   -H "Content-Type: application/json" \
   -H "Authorization: Bearer $OPENROUTER_API_KEY" \
   -d '{
      "model": "google/gemini-3.1-flash-image-preview",
      "messages": [{"role": "user", "content": "Your prompt here"}],
      "modalities": ["image", "text"]
   }'
```

### Specify model
```bash
curl https://openrouter.ai/api/v1/chat/completions \
   -H "Content-Type: application/json" \
   -H "Authorization: Bearer $OPENROUTER_API_KEY" \
   -d '{
      "model": "black-forest-labs/flux.2-pro",
      "messages": [{"role": "user", "content": "A cat in space"}],
      "modalities": ["image", "text"]
   }'
```

### Save the raw API response
```bash
curl https://openrouter.ai/api/v1/chat/completions \
   -H "Content-Type: application/json" \
   -H "Authorization: Bearer $OPENROUTER_API_KEY" \
   -d '{
      "model": "google/gemini-3.1-flash-image-preview",
      "messages": [{"role": "user", "content": "Abstract art"}],
      "modalities": ["image", "text"]
   }' > openrouter-image-response.json
```

### Prompt with stronger constraints
```bash
curl https://openrouter.ai/api/v1/chat/completions \
   -H "Content-Type: application/json" \
   -H "Authorization: Bearer $OPENROUTER_API_KEY" \
   -d '{
      "model": "google/gemini-3.1-flash-image-preview",
      "messages": [{
         "role": "user",
         "content": "Create a cinematic watercolor illustration of a floating city at sunrise. No text, no watermark, no labels, no UI overlays."
      }],
      "modalities": ["image", "text"]
   }'
```

## Request Rules

- Default to `google/gemini-3.1-flash-image-preview`
- Use the Chat Completions endpoint: `https://openrouter.ai/api/v1/chat/completions`
- Include `"modalities": ["image", "text"]`
- Prefer saving the payload to `request.json` and running a reusable script instead of using a one-off inline command
- Put the user request in a single clear `user` message unless a more structured prompt is necessary
- Add a short negative instruction when appropriate, e.g. “No text, no watermark, no labels”
- If the user explicitly wants a different model, honor that request
- If the user wants image editing, use the same OpenRouter workflow and include the source image according to the model's supported multimodal input format
- Tell the user where the created files live, so they can rerun or tweak the request later

## Example Use Cases

### For Scientific Documents
```bash
curl https://openrouter.ai/api/v1/chat/completions \
   -H "Content-Type: application/json" \
   -H "Authorization: Bearer $OPENROUTER_API_KEY" \
   -d '{
      "model": "google/gemini-3.1-flash-image-preview",
      "messages": [{"role": "user", "content": "Microscopic view of cancer cells being attacked by immunotherapy agents, scientific illustration style, no labels or text"}],
      "modalities": ["image", "text"]
   }'
```

### For Presentations and Posters
```bash
curl https://openrouter.ai/api/v1/chat/completions \
   -H "Content-Type: application/json" \
   -H "Authorization: Bearer $OPENROUTER_API_KEY" \
   -d '{
      "model": "google/gemini-3.1-flash-image-preview",
      "messages": [{"role": "user", "content": "Abstract blue and white background with subtle molecular patterns, professional presentation style, no text"}],
      "modalities": ["image", "text"]
   }'
```

### For General Visual Content
```bash
curl https://openrouter.ai/api/v1/chat/completions \
   -H "Content-Type: application/json" \
   -H "Authorization: Bearer $OPENROUTER_API_KEY" \
   -d '{
      "model": "google/gemini-3.1-flash-image-preview",
      "messages": [{"role": "user", "content": "Futuristic AI brain concept with glowing neural networks, high detail, no text or logos"}],
      "modalities": ["image", "text"]
   }'
```

## Error Handling

Common failure cases:
- Missing API key (with setup instructions)
- API errors (with status codes)
- Unsupported or unavailable model IDs
- Unexpected response formats

If a request fails, read the response body first, then adjust the model, payload, or authentication before retrying.

## Critical Prompt Requirements

**IMPORTANT: No Meta Instructions in Output**

When generating prompts for the AI image generation models, ensure the generated image does NOT contain any visible text showing:
- The prompt or instructions that were given to generate it
- System instructions or AI-related metadata
- Any "meta" text describing how the image was created
- Watermarks or labels indicating AI generation
- Layout descriptions (e.g., "left panel", "right panel", "center panel")
- Font specifications or typography instructions
- Color scheme descriptions or palette information

The image should only contain the requested visual content. Always include this instruction in your prompts: "Do not include any text showing the prompt, instructions, layout descriptions, font/color specifications, or metadata in the generated image."

## Notes

- OpenRouter responses may include image data in different shapes depending on the model/version
- Preserve the raw JSON response if you need to inspect where the generated image payload was returned
- Generation time varies by model (typically several seconds to tens of seconds)
- For Windows terminals, `curl.exe` is safer than `curl` in PowerShell
- Reusable scripts are preferred because they make prompt iteration, debugging, and reruns much easier
- Check OpenRouter pricing for cost information: https://openrouter.ai/models

## Image Editing Tips

- Be specific about what changes you want (e.g., "change the sky to sunset colors" vs "edit the sky")
- Reference specific elements in the image when possible
- For best results, use clear and detailed editing instructions
- Use Gemini preview or FLUX.2 Pro when image editing support is needed

## Integration with Other Skills

- **scientific-schematics**: Use for technical diagrams, flowcharts, circuits, pathways
- **generate-image**: Use for photos, illustrations, artwork, visual concepts
- **scientific-slides**: Combine with generate-image for visually rich presentations
- **latex-posters**: Use generate-image for poster visuals and hero images
