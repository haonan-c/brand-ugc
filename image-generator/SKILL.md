---
name: image-generator
description: Generate or edit 1K/2K images from prompts, local images, or public image URLs through an image-generation API. The current backend is EvoLink Nano Banana Pro. Use when Codex needs 生图、图生图、图片编辑、gemini-3-pro-image-preview、Nano Banana Pro，或为 ugc-storyboard、ugc-image-post 生成图片并恢复异步任务。
---

# Image Generation

Run every command below from this Skill's own directory; all relative paths (`scripts/…`, `references/…`) resolve against it.

Create EvoLink async image tasks with `gemini-3-pro-image-preview`, poll for the result, and download it locally right away. The current implementation uses EvoLink and installs alongside `ugc-storyboard` and `ugc-image-post`, sharing a thin adapter with the video Skill.

## Configuration

EvoLink key resolution order:

1. `EVOLINK_API_KEY`
2. `IMAGEGEN_API_KEY` (legacy compatibility)
3. `evolinkApiKey` in the project's `.brand_ugc/credentials.json`
4. legacy `<install>/image-generator/secrets/api_key.txt`

The project credential template is created by `setup-brand-ugc init` and only needs to be filled once; environment variables act as a temporary override. The key must be issued by EvoLink. Never display or log the real key.

## Run

macOS/Linux:

```bash
python3 scripts/generate_image.py \
  --provider nanobanana \
  --prompt-file prompt.txt \
  --image-file reference.png \
  --aspect-ratio 9:16 \
  --resolution 2K \
  --output-dir generated-images
```

Windows PowerShell uses the same arguments; replace `python3` with `python`.

- Fixed model: `gemini-3-pro-image-preview`
- Supported resolutions: `1K`, `2K`
- Default: `2K`
- No automatic downgrade
- Prompts are conservatively trimmed to EvoLink's 2000-token limit
- The task ID is saved to `task.json` in the output directory
- On a repeat run with an existing task ID, only poll and download; do not resubmit

The legacy `--provider nanobanana`, `--image-file`, `--image-url`, `--aspect-ratio`, `--resolution`, and `--output-dir` arguments remain available. EvoLink does not support the old OSS key parameter; stop explicitly if `--osskey` is passed.

See `references/api.md` for the detailed interface contract.
