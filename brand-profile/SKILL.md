---
name: brand-profile
description: Create, validate, read, and resolve reusable local profiles for multiple brands and products, and accumulate consumer insights from interviews, local assets, and topic-radar feedback. Use when Codex needs to 建立品牌档案、保存品牌语气和视觉规范、维护已核实产品卖点与证据、管理禁用表达、沉淀人群痛点与真实用户语言、把选题与评论回流到品牌上下文，或为 ugc-storyboard、ugc-image-post 和 ask-brand 提供一次性不写回的品牌上下文。
---

# Brand Profile

Run every command below from this Skill's own directory; all relative paths (`scripts/…`, `references/…`, `schemas/…`) resolve against it.

Store brand facts, product facts, and marketing constraints in the current project's `.brand_ugc/brands/`.

## Core rules

- Support multiple brands; each brand can contain multiple products.
- Put a statement in `verified_claims` only when it has explicit evidence.
- Task overrides produce temporary context only; they never silently rewrite the long-term profile.
- Saving over an existing profile requires an explicit `--replace`.
- Never display or save API keys, Authorization, Base64, or temporary resource URLs.
- Stable brand facts go in `profile.json`; continuously evolving consumer insights go in `insights.json`.

See `references/profile-contract.md` for the full field reference. Organize the JSON per `schemas/brand-profile.schema.json` when creating or modifying a profile.

## Save a profile

```bash
python3 scripts/manage_profile.py save \
  --profile-file "/absolute/path/to/profile.json" \
  --output-root ".brand_ugc"
```

Add `--replace` when explicitly replacing an existing profile.

## Read a profile

```bash
python3 scripts/manage_profile.py show \
  --brand-id "<brand-id>" \
  --output-root ".brand_ugc"
```

## Resolve task context

When a brand has only one product, `--product-id` may be omitted; when multiple products exist, it is required.

```bash
python3 scripts/manage_profile.py resolve \
  --brand-id "<brand-id>" \
  --product-id "<product-id>" \
  --overrides-file "/absolute/path/to/task-overrides.json" \
  --output-root ".brand_ugc"
```

Overriding `audiences`, `voice`, `visual`, `compliance`, `defaults`, and `product` is allowed; overriding the brand or product ID is not. When `insights.json` exists, the result carries an `insights` block filtered to the current product; task overrides cannot modify it.

## Accumulate consumer insights

Insights come from three channels: operator interviews `interview`, local assets `local_asset`, and platform feedback `platform_radar`. All three first produce a patch, show the user which entries will be added and updated, and merge only after confirmation; nothing is written back automatically.

Organize the patch per `schemas/brand-insights-patch.schema.json`; the rules are in `references/insights-contract.md`. Operator interviews follow `references/interview-guide.md`, asking one question at a time; local assets are distilled per `references/intake-guide.md`; platform feedback is produced by `xhs-topic-radar` after its report completes.

```bash
python3 scripts/manage_profile.py insights-merge \
  --brand-id "<brand-id>" \
  --patch-file "/absolute/path/to/insights-patch.json" \
  --output-root ".brand_ugc"
```

```bash
python3 scripts/manage_profile.py insights-show \
  --brand-id "<brand-id>" \
  --output-root ".brand_ugc"
```

When the same insight is hit again by a **different** observation, its `observed_count` increments and its `confidence` rises, so merging multiple times is expected behavior, not an error; but an observation with identical `source`, `observed_at`, and `ref` counts only once, so accidentally running the same patch twice does not inflate confidence. `platform_radar` reflects category demand rather than an assessment of this brand, so it cannot be written into `differentiation`. When feeding platform content back, keep only summarized statements and phrase-level verbatim quotes; do not store raw comment text or author identifiers.

## Handing off to downstream Skills

Pass the `resolve` output or the absolute path of the brand's `profile.json` downstream. Information provided for a single task takes precedence over the profile; anything not provided stays unverified and is not inferred from product category or benchmark content.
