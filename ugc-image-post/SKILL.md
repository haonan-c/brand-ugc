---
name: ugc-image-post
description: Analyze one benchmark image post and its copy, then create a branded Xiaohongshu-style multi-image publishable candidate from product assets and optional brand profile. Use when Codex needs 对标图文分析、结构级创意迁移、小红书封面与内页组图、产品图锁定、中文确定性排版、标题正文生成、图文视觉QA或继续中断的图文任务。
---

# UGC Image Post

Run every command below from this Skill's own directory; all relative paths (`scripts/…`, `references/…`, `schemas/…`) resolve against it.

Turn an ordered set of benchmark images, benchmark copy, and product images into a brand-specific image-post candidate. By default it produces six 3:4 images, three title candidates, body copy, hashtags, a full-set preview, and a QA report.

## Runtime requirements

- Python 3.10 or newer
- ImageMagick's `magick` command
- The `image-generator` and `ugc-storyboard` Skills
- An EvoLink API key for online generation
- A CJK-capable font: Noto Sans CJK SC, PingFang, or Microsoft YaHei

## Input boundaries

- Benchmark images: required, 1–9 local files, kept in original order.
- Benchmark copy: required, a local text file.
- Product images: required, at least one clear image; a transparent-background PNG composites best.
- Brand profile: optional, from `brand-profile`.
- v1 analyzes exactly one benchmark note per run; it does not scrape platform links and does not blend multiple notes.

Transfer only the hook, narrative, page function, information hierarchy, and visual patterns. Rewrite all copy; do not copy platform UI, avatars, watermarks, the original creator's likeness, trademarks, illustrations, or highly recognizable designs.

## 1. Generate the content plan

Review the benchmark images and copy in order, read `references/content-plan-contract.md`, then write the content plan per `schemas/content-plan.schema.json`.

- Six pages by default; the user may specify 4–9.
- Produce exactly three title candidates; only one advances into visual production.
- Record a source and evidence for each fact.
- The brand profile decides the wording; benchmark content provides method only.
- When `insights.json` exists in the brand-profile directory, the cover hook must come from its audience pain points or content pillars and be written into `hook_basis`; when the insights have accumulated `language_bank.hook_patterns`, the cover's first line must also reuse one of those patterns and be written into `hook_pattern_used`.
- Use `real_composite` for real product compositing; use `ai_interaction` only when interaction is unavoidable.
- Layouts may be chosen only from the controlled components in `references/layouts.md`.

Save the draft to `.brand_ugc/drafts/<run-name>/content-plan.json` is recommended.

## 2. Freeze inputs and wait for confirmation

```bash
python3 scripts/run_pipeline.py \
  --run-name "<run-name>" \
  --reference-image "/absolute/path/reference-01.png" \
  --reference-image "/absolute/path/reference-02.png" \
  --reference-copy-file "/absolute/path/reference-copy.txt" \
  --product-image "/absolute/path/product.png" \
  --plan-file "/absolute/path/content-plan.json" \
  --brand-profile-file "/absolute/path/profile.json" \
  --product-id "<product-id>" \
  --resolution "2K"
```

Omit the matching argument when there is no brand profile. The first run outputs `awaiting_approval`, saves only the inputs and `outputs/内容方案.md`, and calls no image-generation API. Show the plan to the user and wait for confirmation.

## 3. Generate base images

Base-image generation order is: **the runtime's built-in image generation first; only pages it misses fall back to the EvoLink API.**

### 3.1 Export per-page prompts

After the plan is confirmed, use the same arguments plus:

```text
--approve --resume --stage-prompts
```

This outputs `awaiting_backgrounds` and writes `state/background_manifest.json`, which lists each page's `prompt_file`, `output`, `product_mode`, and `reference_image`. This step calls no image-generation interface.

### 3.2 Prefer the runtime's built-in image generation

When the current runtime provides a built-in image tool (e.g. Codex's `image_gen`), generate page by page from the manifest:

- Use the complete prompt in `prompt_file`; do not rewrite it.
- Aspect ratio 3:4, size no smaller than the manifest's `canvas`.
- For pages whose `product_mode` is `ai_interaction`, pass `reference_image` as the reference.
- Save the result to the absolute path given by that page's `output`; the filename must be `image-01.png`.

When the runtime has no built-in image generation, or some pages fail, simply skip those pages.

### 3.3 Generate and lay out

Use the step 2 arguments plus:

```text
--approve --resume
```

The pipeline detects existing base images and skips them; only missing pages call `image-generator` and EvoLink. Pages produced by the built-in tool are recorded as `source: runtime_image_gen` in `state/request_budget.json` and do not consume the EvoLink request budget. Skipping 3.1 and 3.2 and running this step directly sends all pages through the API, matching the old behavior.

- Online generation only creates text-free base images; the real product pixels are composited by local SVG layout.
- `ai_interaction` pages use the product image as a generation reference and require strict visual QA.
- Chinese text, logos, and marketing copy are not drawn by the image model.
- 2K is the default; pass `--resolution 1K` only when the user explicitly accepts it.
- Generate once per page baseline; the full set allows at most two page corrections, and any single page at most one.
- Recovery reuses existing images and the task directory; it does not resubmit.

For development and demos, pass `--offline` to use the local benchmark images as base images and call no paid API.

## 4. Visual QA

After online generation returns `awaiting_visual_qa`, read `references/visual-qa-contract.md`, check all pages, and write a report conforming to `schemas/visual-qa.schema.json`.

Re-run with:

```text
--visual-qa-file "/absolute/path/visual-qa.json" --approve --resume
```

A failing report triggers at most two page corrections, and a corrected image still needs re-review. Only a passing report marks the online task `completed`. Stop auto-correction when three or more pages have major issues.

## Final deliverables

The user-facing files live in `.brand_ugc/<run-name>/deliverables/`:

- `page-01.png` through the last page
- `整组预览.png`
- `发布文案.md`
- `图文内容.json`
- `QA报告.json`

The final reply shows the full-set preview directly and gives the publish copy and the deliverables directory. Do not publish to any platform automatically.
