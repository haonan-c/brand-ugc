---
name: ask-brand
description: Entry-point router for brand content production. Diagnose the request, check local assets, then hand off to exactly one xhs-topic-radar, brand-profile, ugc-image-post, or ugc-storyboard run. Use when the target format is still undecided or the request is vague — 帮我做点品牌内容、你看着办、不知道该做图文还是短视频、先看看我素材够不够、不知道从哪开始、同时要选题研究又要成品。When the user already names one workflow, go straight to that Skill instead of this one.
---

# Ask Brand

Run every command below from this Skill's own directory; all relative paths (`scripts/…`, `references/…`, `schemas/…`) resolve against it.

Serve as the unified entry point for brand content production. Handle diagnosis, asset checks, and orchestration; do not duplicate the production logic of downstream Skills.

## Routing principles

- When the user explicitly asks for topics (including "need / want / help me find topics for some industry"), the topic radar, daily topics, demand keywords, or topic research, go straight to `xhs-topic-radar`; do not misread an industry term as a request to name software, a project, or a product.
- When the user explicitly asks for an image post, go straight to `ugc-image-post`.
- When the user explicitly asks for a short video or storyboard, go straight to `ugc-storyboard`.
- When the user explicitly asks to create or update a brand profile, go straight to `brand-profile`.
- When the user wants both topic research and finished production, ask only one ordering question; recommend doing topics first, then let the user pick a strategy card.
- When the request is vague, offer one recommended path and ask only one key question at a time.
- Do not generate both an image post and a video by default.
- Do not force an interruption when there is no brand profile; single-task information can be used to continue.
- When the brand profile has multiple brands or products and the user has not specified one, ask only for the brand or product needed.

See `references/routing-contract.md` for the detailed rules.

## Asset diagnosis

Run this when a repeatable check is needed:

```bash
python3 scripts/route_request.py \
  --request "<用户原始需求>" \
  --reference-image "/absolute/path/reference.png" \
  --reference-copy-file "/absolute/path/copy.txt" \
  --reference-video "/absolute/path/reference.mp4" \
  --product-image "/absolute/path/product.png" \
  --brand-profile-file "/absolute/path/profile.json"
```

Read the result per `schemas/route-decision.schema.json`:

- `ready`: execute `recommended_skill` directly; do not re-confirm the path.
- `needs_input`: ask only for the required assets listed in `missing_inputs`.
- `needs_confirmation`: give the `question` to the user verbatim and wait for an answer before routing. Do not swap in your own question, do not append another question in the same turn, and do not pick a default answer and continue for the user.

## Setup orchestration

`ready` means the route is decided, not that the downstream environment is ready. On the first entry into a recommended Skill, delegate to `setup-brand-ugc` to create or reuse the project-level `.brand_ugc/credentials.json` and run the read-only preflight for the target path. `setup-brand-ugc` owns all credential rules — field names, resolution order, and leaked-key handling; do not restate them here. Initialization is a prerequisite step of the recommended workflow, not a second content-production path.

## Orchestration

### `xhs-topic-radar`

First query real search-autocomplete demand keywords; after the user explicitly approves the remaining cost, collect notes and comments and generate strategy cards backed by evidence and a creative structure. It does not generate images or publish content directly. After the report completes, it may ask once whether to feed this run's consumer language back into brand insights.

### `brand-profile`

Create, save, or resolve brand and product profiles, and accumulate consumer insights from interviews, local assets, and platform feedback. Neither task overrides nor insights are written back to the long-term profile automatically.

### `ugc-image-post`

Requires benchmark images, benchmark copy, and product images. Handles content-plan confirmation, image-post generation, layout, QA, and recovery.

### `ugc-storyboard`

Requires a benchmark video and product images. Handles the twelve-panel storyboard and the Seedance prompt.

After routing, follow the downstream Skill's inputs, confirmation points, cost limits, and stop conditions. Summarize the downstream deliverables at the end, but do not have `ask-brand` call TikHub, image-generation APIs, or rewrite downstream state directly. After the topic radar finishes, start a separate image-post or video production run only when the user explicitly picks a strategy card and confirms the content format.
