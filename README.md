<p align="right">
  <strong>English</strong> · <a href="README.zh-CN.md">简体中文</a>
</p>

<p align="center">
  <img src="assets/brand-ugc-workflow.png" alt="Brand UGC content production workflow" width="100%">
</p>

# brand-ugc

Diagnose a brand marketing request from one entry point, then turn a benchmark
video or image post into brand-specific content.

This repository contains seven composable Agent Skills, ready to use in both Codex and Claude Code:

- `setup-brand-ugc` checks local dependencies, installed Skills, and credential status, then guides first-time setup.
- `ask-brand` diagnoses the request, checks assets, and routes one workflow.
- `xhs-topic-radar` discovers Xiaohongshu demand language and produces evidence-backed daily topic strategy cards.
- `brand-profile` maintains reusable local profiles for multiple brands and products.
- `ugc-image-post` creates Xiaohongshu-style image-post candidates, copy, previews, and QA.
- `ugc-storyboard` creates 12-panel video storyboards and Seedance prompts.
- `image-generator` is the shared EvoLink image-generation adapter.

> [!IMPORTANT]
> The image-post workflow creates publishable candidates but does not post them.
> The video workflow creates storyboards and prompts but does not render the final MP4.

## How it works

The suite separates deciding what to make, storing verified brand facts, producing
content, and calling image-generation services. You can start from one router or
invoke a production Skill directly when the target format is already clear.

```mermaid
flowchart LR
    U["Marketing request and local assets"] --> A["ask-brand<br/>Diagnosis and routing"]
    A --> T["xhs-topic-radar<br/>Demand and topic research"]
    A --> P["brand-profile<br/>Create or resolve a profile"]
    A --> I["ugc-image-post<br/>Image-post production"]
    A --> V["ugc-storyboard<br/>Video storyboard"]
    T --> S["User-selected strategy card"]
    S -. "Separate approved production run" .-> I
    S -. "Separate approved production run" .-> V
    P -. "Brand rules and verified facts" .-> I
    P -. "Brand rules and verified facts" .-> V
    I --> G["image-generator<br/>Shared generation capability"]
    V --> G
    I --> DI["Image-post candidate + QA"]
    V --> DV["12-panel board + Seedance prompt"]
```

| Type | Skill | When to use it |
| --- | --- | --- |
| Setup | `setup-brand-ugc` | Run once after installing, to check dependencies and configure EvoLink/TikHub credentials |
| Unified entry | `ask-brand` | The request or assets are unclear, or you need to choose research, image post, or video |
| Research entry | `xhs-topic-radar` | Discover demand terms and create evidence-backed Xiaohongshu topic strategy cards |
| Brand context | `brand-profile` | Create, update, or select reusable brand and product facts |
| Production entry | `ugc-image-post` | The request is clearly a benchmark image-post transfer |
| Production entry | `ugc-storyboard` | The request is clearly a benchmark video storyboard |
| Shared capability | `image-generator` | Called by production Skills; usually not invoked directly |

The operating rules are simple: choose one production path at a time, approve the
plan before paid generation, keep claims traceable, and save resumable state locally.

## Quickstart

### 1. Requirements

- [Codex](https://openai.com/codex/) or [Claude Code](https://code.claude.com/); or
  `@earendil-works/pi-coding-agent` for the evaluation-stage Pi Agent path
- Node.js and `npx`; topic radar requires Node.js `>=22.5.0`, while other paths use Node only for installation
- Python 3.10 or newer
- Image posts: ImageMagick and a CJK font such as Noto Sans CJK SC
- Video: FFmpeg and FFprobe
- Topic radar: a user-owned [TikHub API Key](https://api.tikhub.io/)
- Online generation: an [EvoLink API Key](https://evolink.ai/dashboard/keys)

### 2. Install all Skills

Pick the agent you use.

**Codex**

```bash
npx -y skills@latest add haonan-c/brand-ugc \
  --skill setup-brand-ugc ask-brand xhs-topic-radar brand-profile ugc-image-post ugc-storyboard image-generator \
  --agent codex --global --yes
```

Fully restart Codex or open a new task, then verify:

```bash
npx -y skills@latest list --global --agent codex
```

**Claude Code**

```bash
npx -y skills@latest add haonan-c/brand-ugc \
  --skill setup-brand-ugc ask-brand xhs-topic-radar brand-profile ugc-image-post ugc-storyboard image-generator \
  --agent claude-code --global --yes
```

Start a new Claude Code session, then verify:

```bash
npx -y skills@latest list --global --agent claude-code
```

**Pi Agent** (evaluation stage — see [`docs/pi-agent-driver-evaluation.md`](docs/pi-agent-driver-evaluation.md))

```bash
npm install -g @earendil-works/pi-coding-agent@0.82.1
npx -y skills@latest add haonan-c/brand-ugc \
  --skill setup-brand-ugc ask-brand xhs-topic-radar brand-profile ugc-image-post ugc-storyboard image-generator \
  --agent pi --global --yes
```

Verify:

```bash
npx -y skills@latest list --global --agent pi
```

Pin the exact `pi-coding-agent` version above; the package is still `0.x` and the
evaluation doc's compatibility notes assume this version. Pi is being evaluated as the
driver behind brand-ugc's own operations workbench (see
[ADR 0003](docs/adr/0003-pi-agent-is-the-autonomous-controller.md)), not yet a
production install target — treat it as a PoC path, not the default recommendation.

Drop `--global` from any of the commands above to install into the current project
only (`.claude/skills/`, or `.pi/skills/` for Pi) instead of user-level. The SKILL.md
files are identical across all three agents; no adaptation is needed.

> In Claude Code, Skills are matched automatically from their `description`, so you
> can just describe the task in plain language, or say "use the ask-brand skill".
> Pi does not always read a Skill's full body automatically either; when you need a
> specific one to run, trigger it explicitly (`/skill:ask-brand`, etc.). The
> `$skill-name` shorthand in the examples below is Codex's own invocation syntax.

### 3. Run first-time setup

Use `$setup-brand-ugc`: it checks whether Python, Node.js, ImageMagick, a CJK font, and
FFmpeg/FFprobe are present, lists install commands for anything missing, and guides
EvoLink and TikHub credential setup, so you do not have to check each dependency by hand.

You can also configure EvoLink manually:

```bash
export EVOLINK_API_KEY="<YOUR_EVOLINK_KEY>"
```

Alternatively, save the key by itself at:

```text
Windows:      %USERPROFILE%\.agents\skills\image-generator\secrets\api_key.txt
macOS/Linux:  ~/.agents/skills/image-generator/secrets/api_key.txt
```

Never paste a real key into chat, screenshots, logs, or Git.

### 4. Start from the router

```text
Use $ask-brand to decide whether these launch assets should become an image post
or a short video first, then continue with the recommended workflow.

I uploaded:
1. Product images
2. Benchmark images and copy, if available
3. A benchmark video, if available
4. A brand profile, if available
```

You can invoke either production Skill directly when the desired format is clear.

## Recommended workflow

### First-time setup

1. Install all seven Skills, then run `$setup-brand-ugc` to verify the local dependencies for the intended path.
2. Use `$setup-brand-ugc` to configure a TikHub key for topic research and an EvoLink key for online generation; an offline image-post demo can run without EvoLink.
3. Optionally use `$brand-profile` to save voice, prohibited language, product facts, and evidence.
4. Prepare one task's assets. Do not mix image-post and video benchmarks in one production run.
5. Start from `$ask-brand` when the path is unclear, or invoke a production Skill directly.

### Every content run

1. **Diagnose:** confirm the format, brand or product, required assets, and missing input.
2. **Plan:** analyze the benchmark's method and create an original branded plan.
3. **Approve:** review structure, copy direction, and facts before paid generation.
4. **Produce:** generate and compose image-post pages or create the video storyboard.
5. **QA:** check facts, brand consistency, visual integrity, and set coherence; retry within limits.
6. **Deliver:** save candidates, structured data, previews, and QA locally.

An online image-post run moves through these states:

| State | Meaning | Next action |
| --- | --- | --- |
| `awaiting_approval` | The plan is saved and no generation API was called | Approve, then continue with `--approve --resume` |
| `awaiting_visual_qa` | Online generation and local composition are complete | Inspect every page and submit visual QA |
| `completed` | Visual QA passed and deliverables were collected | Use the files in `deliverables/` |

If a command returns an error, fix the input, dependency, or generation problem.
Resume the existing run only when its inputs have not changed; otherwise start a new run.

## First-time setup workflow

After installing, or on a new machine, use `$setup-brand-ugc`:

```text
Use $setup-brand-ugc to check dependencies and configure the credentials I need this time.

I plan to use: image post (or short video / topic radar / all of them).
```

It never produces content or calls a paid API. It asks which path you intend to use,
actively checks only the system dependencies that path needs, reports which of the six
production Skills are installed, and completes every setup step that does not require a
secret. For TikHub, the Agent starts or provides one hidden-input command; you enter the
key only in a trusted terminal, then the Agent verifies it and resumes the original task.
It never asks you to paste a real key into chat.

## Topic-radar workflow

Use `$xhs-topic-radar` when you need evidence-backed directions before producing a post. It asks for an industry and lookback period, spends only the bounded autocomplete preview first, and stops for explicit approval before note/comment collection. The default software-copyright run is capped at 27 TikHub business requests and US$0.30.

Each final strategy card includes audience, target scenario, sample-relative rationale, concrete evidence interpretation, exact Xiaohongshu source URLs, autocomplete demand language, title and writing frameworks, hook, outline, CTA, six-part weighted scoring, and policy/claim guardrails. Reports are saved under `.brand_ugc/topic-radar/reports/`.

A single search snapshot is not precise search volume or proof of a platform-wide trend. Social posts are not policy authority. After the report is complete, select one card before starting a separate image-post or storyboard run.

See [`docs/xhs-topic-radar.md`](docs/xhs-topic-radar.md) for CLI, credentials, cost controls, and local state.

## Image-post workflow

Provide one ordered set of benchmark images, its copy, and a product image:

```text
Use $ugc-image-post to create a Xiaohongshu-style branded image-post candidate.

Transfer only the structure and creative method. Do not copy wording, people,
trademarks, watermarks, or platform UI. Create six 3:4 pages and three title
options by default. Show me the content plan before paid generation.
```

The workflow:

1. Analyzes the hook, page roles, narrative, hierarchy, and visual patterns.
2. Creates a 4–9 page plan, defaulting to six.
3. Waits for approval before image generation.
4. Generates text-free backgrounds and composes real product pixels, text, and logos locally.
5. Runs group QA, with at most two page retries and one retry per page.
6. Delivers individual pages, a preview, publish copy, structured content, and QA.

Online runs require a visual QA report before they are marked complete. All run data
lives under `.brand_ugc/<run-name>/`; final files are collected in `deliverables/`.

## Video workflow

Provide a benchmark video and product image:

```text
Use $ugc-storyboard to create a 15-second brand UGC storyboard.

Return a 2K 12-panel storyboard and the complete Seedance prompt. Do not add
unsupported claims, subtitles, watermarks, or platform UI.
```

The existing seven-stage workflow remains intact: video analysis, local frame
extraction, rewritten script, 12 image prompts, template storyboard, final storyboard,
and video prompt.

## Brand profiles

`brand-profile` stores voice, colors, fonts, logos, prohibited language, and verified
product claims under:

```text
.brand_ugc/brands/<brand-id>/profile.json
```

Multiple brands and products are supported. Task overrides do not silently rewrite
the saved profile. Every verified claim must include evidence.

## Inputs and outputs

| Path | Required input | Main output |
| --- | --- | --- |
| Topic radar | Industry, lookback period, TikHub key, explicit collection approval | 10 evidence-backed strategy cards, Markdown/JSON report, local evidence pack |
| Image post | 1–9 benchmark images, benchmark copy, product image | 4–9 3:4 pages, three titles, copy, preview, JSON, QA |
| Video | Benchmark video, product image | 2K storyboard, Seedance prompt, 12 motion instructions, QA |
| Brand profile | Brand ID, brand name, products | Reusable `profile.json` and resolved task context |

Person images, brand profiles, and additional verified facts are optional.

## Privacy, cost, and quality

- Topic radar performs a three-request autocomplete preview first and requires explicit approval before the remaining bounded TikHub collection.
- Topic evidence and reports remain local; exact note URLs are preserved for traceability.
- Original video stays local; only a derived proxy and optional mono audio are analyzed remotely.
- Benchmark post images are not sent as online generation references; product references are sent only for interaction pages.
- Logs must not contain API keys, authorization headers, Base64, or temporary URLs.
- 2K is the default and is never silently downgraded.
- A six-page image post uses six base generations and at most two page retries.
- A video run is capped at the configured 14 model business requests.
- Missing product facts remain unverified; the workflows do not invent claims.

## Advanced CLI

Codex first creates a Schema-valid image-post plan, then runs:

```bash
python3 ~/.agents/skills/ugc-image-post/scripts/run_pipeline.py \
  --run-name "my-product-post" \
  --reference-image "/absolute/path/reference-01.png" \
  --reference-copy-file "/absolute/path/reference-copy.txt" \
  --product-image "/absolute/path/product.png" \
  --plan-file "/absolute/path/content-plan.json"
```

The first run waits for approval. Repeat it with `--approve --resume` after approval.

After online generation, Codex inspects every page and creates a visual QA file.
Repeat the same command with:

```text
--visual-qa-file "/absolute/path/visual-qa.json" --approve --resume
```

To recover an interrupted run, keep the same `--run-name` and original inputs, then
use `--resume`. Use a new run name when changing the benchmark, product, or content
plan so that two runs do not share state.

Video:

```bash
python3 ~/.agents/skills/ugc-storyboard/scripts/run_public_pipeline.py \
  --run-name "my-product-ugc" \
  --video "/absolute/path/reference.mp4" \
  --product-image "/absolute/path/product.png" \
  --brand-profile-file "/absolute/path/profile.json" \
  --brand-product-id "<product-id>" \
  --product-info "Verified product facts and restrictions" \
  --resolution "2K"
```

## Local data and deliverables

```text
.brand_ugc/
├── brands/<brand-id>/profile.json
├── topic-radar/          Config, raw evidence, SQLite history, pending packs, and reports
├── drafts/<run-name>/content-plan.json
└── <run-name>/
    ├── inputs/          Pinned inputs and manifest
    ├── outputs/         Content plan and intermediate output
    ├── images/          Base, product, and composed images
    ├── state/           Run state and request budget
    └── deliverables/    Final images, copy, JSON, preview, and QA
```

Runs do not overwrite unrelated task directories by default. Share `deliverables/`
rather than publishing a whole run directory that may contain source assets, state,
or local secret paths.

## Troubleshooting

**Why did the first run create no images?**

Stopping at `awaiting_approval` is expected. The first run only pins inputs and
presents the content plan; paid requests begin after approval.

**Why are the images ready while the run is not complete?**

Online runs require group visual QA. At `awaiting_visual_qa`, ask Codex to inspect
the pages and resume with the QA file. Only a passing report reaches `completed`.

**Can I work without a brand profile?**

Yes. Brand details supplied in the task become temporary context and are not
silently written to a long-lived profile.

**Why does the workflow ask me to select a product?**

When a profile contains multiple products, a `product-id` is required to prevent
facts and assets from different products from being mixed.

**Why do Chinese characters render as boxes, or why does ImageMagick fail?**

Install Noto Sans CJK SC or another supported CJK font and verify `magick -version`.
For video-analysis failures, also verify `ffmpeg` and `ffprobe`. Run `$setup-brand-ugc`
to check all of these at once and get the matching install commands.

**Do I have to install dependencies and configure keys by hand on first run?**

No. After installing the Skills, run `$setup-brand-ugc` first. It checks dependencies,
reports what is missing with install commands, and guides EvoLink and TikHub credential
setup; it only asks about the path you actually intend to use.

**Can the workflow publish directly to Xiaohongshu or another platform?**

No. It produces candidates and QA only; account login, automated publishing, and
platform scraping are outside the current scope.

## Development

```bash
PYTHONPATH=. uv run --with pytest pytest -q
```

Repository layout:

```text
setup-brand-ugc/  Dependency checks and first-time credential setup
ask-brand/        Unified diagnosis and orchestration
xhs-topic-radar/  Xiaohongshu demand discovery and topic strategy reports
brand-profile/    Multi-brand, multi-product profiles
ugc-image-post/   Planning, generation, composition, QA, and resume
ugc-storyboard/   Seven-stage video storyboard workflow
image-generator/  EvoLink image-generation adapter
tests/            Contract, CLI, resume, and offline end-to-end tests
examples/         Licensed or source-documented fixtures
docs/             API compatibility notes
```

## License

Original project code is available under the [MIT License](LICENSE). Adapted material
retains its upstream licenses; see
[`ugc-storyboard/THIRD_PARTY_NOTICES.md`](ugc-storyboard/THIRD_PARTY_NOTICES.md).
