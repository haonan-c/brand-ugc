---
name: ugc-storyboard
description: Generate a final 12-panel brand UGC storyboard image and a production-ready 15-second Seedance prompt from a benchmark video, product image, optional person image, copy, product notes, and optional brand profile. Use when Codex needs to analyze or adapt a 品牌 UGC 短视频、生成十二宫格分镜、替换商品或人物、应用品牌档案、运行 EvoLink 多模态分析和生图流程，或继续一个中断的分镜任务。
---

# UGC Storyboard

Run every command below from this Skill's own directory; all relative paths (`scripts/…`, `references/…`, `schemas/…`) resolve against it.

Run the seven-stage brand UGC video adaptation flow, finally delivering a twelve-panel storyboard image and a Seedance video prompt. It does not produce the final MP4.

## First-time configuration

Run `setup-brand-ugc init` to create the project credential template and fill `evolinkApiKey`; `setup-brand-ugc` owns the credential setup flow.

EvoLink key resolution order:

1. `EVOLINK_API_KEY`
2. `IMAGEGEN_API_KEY` (legacy compatibility)
3. `evolinkApiKey` in the project's `.brand_ugc/credentials.json`
4. legacy `<install>/image-generator/secrets/api_key.txt`

Environment variables act as a temporary override. The key must be issued by EvoLink; never display it in chat, logs, or prompts. Also confirm this machine has Python 3.10 or newer, FFmpeg, and FFprobe installed.

## Inputs

- Benchmark video: required, kept locally only and used for frame extraction.
- Product image: required.
- Person image: optional; when provided, locks person consistency.
- Copy file: optional.
- Product notes: recommended, using only facts directly visible in the user's text and the product image.
- Brand profile: optional; supplements brand voice, visual constraints, verified facts, and banned expressions.

## Run

macOS/Linux:

```bash
python3 scripts/run_public_pipeline.py \
  --run-name "<run_name>" \
  --video "<benchmark_video.mp4>" \
  --product-image "<product.png>" \
  --person-image "<optional_person.jpg>" \
  --copy-file "<optional_copy.txt>" \
  --brand-profile-file "<optional_brand_profile.json>" \
  --brand-product-id "<optional_product_id>" \
  --product-info "<product name, verifiable selling points, and limits>" \
  --resolution "2K"
```

Windows PowerShell:

```powershell
python scripts\run_public_pipeline.py `
  --run-name "<run_name>" `
  --video "<benchmark_video.mp4>" `
  --product-image "<product.png>" `
  --person-image "<optional_person.jpg>" `
  --copy-file "<optional_copy.txt>" `
  --brand-profile-file "<optional_brand_profile.json>" `
  --brand-product-id "<optional_product_id>" `
  --product-info "<product name, verifiable selling points, and limits>" `
  --resolution "2K"
```

Do not overwrite an existing run of the same name. After an explicit `--resume`, continue only the unfinished stages; when an EvoLink image task ID already exists, only poll, do not resubmit.

When the brand profile has only one product, `--brand-product-id` may be omitted. Without a brand profile the behavior is identical to the original flow; with one, the current task's product info takes precedence while the profile supplements long-term constraints and is never written back.

By default all task data is saved under the current project's `.brand_ugc/<run_name>/`, including input copies, intermediate artifacts, generated results, QA, progress, and resume state. Do not create brand UGC task artifacts outside this directory. Pass `--output-root` only when the user explicitly specifies another location.

`2K` is the default quality. Use `--resolution 1K` only when the user explicitly accepts lower quality; automatic downgrade from 2K is forbidden.

## Seven stages

1. Video parse: locally produce a silent proxy up to 720p and a mono audio track; the original video is not uploaded; outputs `outputs/12镜头解析.json` and `outputs/12镜头解析.md`.
2. Twelve-panel reference: locally extract 12 frames from the original video; outputs `collages/12宫格参考图.jpg`.
3. New storyboard script: outputs the JSON source of truth and `outputs/新产品-12分镜脚本.md`.
4. Twelve-panel prompts: outputs the JSON source of truth and `outputs/1-12分镜提示词.md`.
5. First-pass template image: generate the 2K twelve-panel and run visual QA; at most one correction generation.
6. Final storyboard image: composite the product and optional person and run visual QA; at most one correction generation.
7. Video prompt: output one ready-to-use 15-second Seedance master prompt and 12 per-shot motion instructions to `outputs/视频提示词1-12.txt`.

After the flow completes, summarize the final twelve-panel storyboard image, the full video prompt, and the final QA report into `deliverables/`. If any report or file organizing is needed outside the pipeline, it must still be saved in the same task directory; the final user-facing files go in `deliverables/`.

Keep the user-visible progress words unchanged:

`视频解析完成`、`12宫格参考图完成`、`新分镜脚本完成`、
`12分镜提示词完成`、`第一步模板图完成`、`最终分镜图完成`、
`视频提示词完成`.

## Contracts and stop conditions

- The internal JSON is the single source of truth; Markdown/TXT is rendered only from JSON that passes the schema.
- Each structured stage must contain exactly 12 consecutive, non-overlapping shots.
- A schema failure is auto-repaired only once; a second failure stops.
- Each image stage's QA failure triggers only one correction generation; a second failure keeps the image and report and stops.
- A single run uses at most the 14 model business requests set in the config; stop when the cap is reached.
- Check the EvoLink balance before running.
- Logs must not contain keys, Authorization, Base64, or temporary resource URLs.

Before changing stage rules, read `references/prompt-contract.md`. Read the relevant module in `references/stages/` only when the corresponding stage needs to run.

## Final reply

On success, send directly in chat:

```markdown
![最终12宫格分镜图](/absolute/path/to/.brand_ugc/<run_name>/deliverables/最终12宫格分镜图.png)

视频提示词：
<完整总提示词>
```

Also note that the 12 detailed motion instructions are saved to `.brand_ugc/<run_name>/deliverables/视频提示词1-12.txt`.
