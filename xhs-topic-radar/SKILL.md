---
name: xhs-topic-radar
description: Discover Xiaohongshu autocomplete demand language, collect bounded TikHub note/comment evidence, and generate evidence-backed daily topic strategy cards. Use when users ask for 小红书每日选题、选题雷达、热点选题、需求词、搜索联想、话题研究，或希望先研究选题再进入品牌图文/短视频生产。
---

# Xiaohongshu Topic Radar

Use this Skill for topic discovery and evidence-backed planning. It does not publish content and does not call image-generation services.

## Runtime

- Node.js `>=22.5.0` is required (`node:sqlite` is used).
- TikHub access requires the user's own `TIKHUB_API_KEY`.
- Never ask the user to paste a real key into chat, logs, screenshots, or command-line arguments. If one is exposed there, do not use it; require revocation and a fresh key.
- State is local to `<brand-workspace>/.brand_ugc/topic-radar/`.

Resolve every relative path in this file against this Skill directory. The CLI is:

```bash
node scripts/topic_radar.mjs <command> --workspace "/absolute/brand/workspace"
```

## Guided workflow

### 1. Configure

If the user has not chosen an industry and lookback period, ask for them before any paid request. Supported lookback is 1–180 days; recommend 7 days by default.

```bash
node scripts/topic_radar.mjs setup \
  --workspace "/absolute/brand/workspace" \
  --industry "<industry>" \
  --lookback-days 7
```

Software-copyright industries keep the 4/3/3 audience quotas for students, high-tech enterprises, and Hangzhou E-class talent. Other industries use ten general-audience topics.

### 2. Configure the TikHub key safely

First run `key status` yourself with the brand workspace. Credential precedence is `TIKHUB_API_KEY`, project-local `.brand_ugc/credentials.json`, then the legacy user-level credential file:

```bash
node scripts/topic_radar.mjs key status --workspace "/absolute/brand/workspace"
```

If the project file does not exist, use `setup-brand-ugc init` to create its protected template and ask the user to fill `tikhubApiKey` once in a trusted editor. Every later radar command reads it automatically. Alternatively, start the hidden-input command below; it updates the same project file:

```bash
node scripts/topic_radar.mjs key set --workspace "/absolute/brand/workspace"
```

If you cannot expose an interactive terminal, give only that one command for the user to run in a trusted terminal. Do not ask them to paste the key into chat, repeat the shell-pipeline form, run `key status`, or reply with an exact phrase. On their next message, run `key status` yourself. Once configured, continue automatically with the original topic-radar request without asking them to restate it.

For non-interactive automation, `key set` still accepts the key through stdin. Omitting `--workspace` preserves the legacy user-level behavior. It never accepts a key as a command-line argument.

### 3. Preview demand terms, then stop

```bash
node scripts/topic_radar.mjs preview \
  --workspace "/absolute/brand/workspace"
```

This stage performs only the bounded autocomplete discovery requests (normally three). Present the exact returned seeds and suggestion terms, requests already spent, estimated cost already spent, remaining maximum requests, and remaining estimated cost.

**Stop and wait for explicit user approval.** Do not infer approval from the original request. If a matching report already exists, show its path; only use `--force` after the user explicitly requests a paid refresh.

### 4. Collect only after approval

```bash
node scripts/topic_radar.mjs collect \
  --workspace "/absolute/brand/workspace" \
  --plan "/absolute/path/from-preview.json" \
  --approve
```

The CLI rejects collection without `--approve` and validates that the plan is current and matches the configuration. It preserves the hard caps of 27 TikHub business requests and US$0.30, performs official pricing and balance preflight, paces paid calls, saves raw responses, samples comments, records partial failures, and writes a pending evidence pack.

### 5. Generate strategy cards

Read the pending evidence pack completely. Follow its `industry`, `outputCount`, `audienceLabels`, and `audienceQuotas` exactly. Create a JSON array that validates against `schemas/topic-candidates.schema.json`.

For every topic:

- cite at least one exact, unmodified `noteUrl` from `evidence`; prefer two mutually supporting sources;
- copy `demandKeywords` only from the matching audience's `searchSuggestions.seed` or `terms`;
- explain what the cited notes/comments concretely support in `evidenceSummary`;
- use `marketOverview` and `keywordBenchmarks` only for relative judgments within this finite sample;
- make `contentGap` an explicitly cautious sample-based strategy inference;
- avoid exact and semantic repetition with `recentTopicTitles` and with other topics in the same report;
- provide target scenario, format, structure, title pattern, writing framework, hook, must-cover points, outline, and a non-misleading CTA;
- score all six dimensions and calculate:

```text
round(demandFit×25% + evidenceStrength×20% + timingFit×15%
    + differentiation×15% + executability×15% + riskSafety×10%)
```

Priority is `high` at 80+, `medium` at 65–79, and `low` below 65.

Autocomplete is demand-language evidence, not precise search volume. A single snapshot does not establish a platform-wide trend, algorithm preference, or guaranteed viral result. Xiaohongshu posts are social evidence, never factual, legal, or policy authority. For price, timing, eligibility, effects, policy, or compliance, require current official or authoritative verification and prohibit outcome guarantees in both `riskNote` and `doNotSay`.

Save the generated array to a local draft file, for example:

```text
.brand_ugc/topic-radar/data/drafts/<run-id>-topics.json
```

### 6. Finalize through the validator

```bash
node scripts/topic_radar.mjs finalize \
  --workspace "/absolute/brand/workspace" \
  --run-id "<run-id>" \
  --topics-file "/absolute/topics.json"
```

Do not hand-write the final report. The validator enforces counts, quotas, exact evidence URLs, audience demand keywords, required strategy-card fields, weighted scores, priorities, risk guards, and recent-title duplication before writing Markdown/JSON and updating SQLite state.

### 7. Report completion concisely

Return only a short summary with:

- report path;
- Top 3 topics;
- TikHub request count and estimated cost;
- evidence count;
- collection error count.

Do not paste the full report into chat.

## Inspection and recovery

```bash
node scripts/topic_radar.mjs status --workspace "/absolute/brand/workspace"
node scripts/topic_radar.mjs report --workspace "/absolute/brand/workspace"
node scripts/topic_radar.mjs report --workspace "/absolute/brand/workspace" --date YYYY-MM-DD
node scripts/topic_radar.mjs config --workspace "/absolute/brand/workspace"
```

A failed or interrupted run remains inspectable in SQLite and local files. Reuse a preview plan only on the same local date and with the same configuration. Run a new preview after changing industry, lookback period, queries, quotas, or evidence limits.

## Handoff to production

After the user chooses one finalized strategy card, pass only that card and verified brand facts into a separate `ugc-image-post` or `ugc-storyboard` run. Do not silently begin paid content generation, and do not mix topic-radar state with production run directories.

Detailed state and safety rules are in `references/workflow-contract.md`; field guidance is in `references/topic-card-contract.md`.
