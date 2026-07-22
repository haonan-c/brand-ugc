<p align="right">
  <strong>English</strong> · <a href="README.zh-CN.md">简体中文</a>
</p>

<p align="center">
  <img src="assets/brand-ugc-workflow.png" alt="Reference video and product assets becoming a 12-panel storyboard and production prompt" width="100%">
</p>

# brand-ugc

Turn a reference UGC video and product assets into a brand-specific 12-panel
storyboard and a production-ready 15-second Seedance prompt.

`brand-ugc` is a Codex skill for brand marketers and UGC creators. It analyzes a
reference video, adapts the creative to a new product and optional person, generates
and validates a final storyboard, then writes the master video prompt and 12
shot-level motion instructions.

> [!IMPORTANT]
> The current version does **not** render the final MP4. It prepares the storyboard
> and prompts you can take into Seedance.

## Quickstart

### 1. Check the prerequisites

- [Codex](https://openai.com/codex/)
- Node.js and `npx` — required only for the one-command installer
- Python 3.10 or newer
- FFmpeg and FFprobe
- An [EvoLink API Key](https://evolink.ai/dashboard/keys)

You do not need to configure any models manually.

### 2. Install both skills globally

Run this command once:

```bash
npx -y skills@latest add haonan-c/brand-ugc --skill brand-ugc imagegen-api --agent codex --global --yes
```

This installs both required skills:

- `brand-ugc` — the seven-stage UGC workflow
- `imagegen-api` — the EvoLink image-generation adapter used by the workflow

### 3. Configure the EvoLink API Key

The recommended method is the `EVOLINK_API_KEY` environment variable.

macOS/Linux, for the current shell:

```bash
export EVOLINK_API_KEY="<YOUR_EVOLINK_KEY>"
```

Add the same export to the shell profile you use to launch Codex if you want it to
persist.

Windows PowerShell, for the current user:

```powershell
[Environment]::SetEnvironmentVariable("EVOLINK_API_KEY", "<YOUR_EVOLINK_KEY>", "User")
```

Restart Codex after setting a persistent environment variable.

As a fallback, save the key by itself in this local file:

```text
Windows:      %USERPROFILE%\.codex\skills\imagegen-api\secrets\api_key.txt
macOS/Linux:  ~/.codex/skills/imagegen-api/secrets/api_key.txt
```

Never paste a real key into chat, screenshots, logs, or Git.

### 4. Ask Codex to create the storyboard

Upload a reference video and product image, then send:

```text
Use $brand-ugc to create a 15-second brand UGC storyboard.

I uploaded:
1. A reference video
2. A product image
3. A person reference image (optional)
4. Copy or a copy file (optional)

Product name:
<name>

Verified product notes:
- <facts visible in the product image or supplied by me>

Use 2K output. Do not add unsupported claims, subtitles, watermarks, or platform UI.
Return the final 12-panel storyboard and the complete Seedance master prompt.
```

## Inputs and outputs

| Type | Item | Required |
| --- | --- | --- |
| Input | Reference UGC video, usually around 15 seconds | Yes |
| Input | Product image or product contact sheet | Yes |
| Input | Person reference image | No |
| Input | Copy, product facts, and constraints | No, but recommended |
| Output | Final 2K 12-panel storyboard | Yes |
| Output | 15-second Seedance master prompt | Yes |
| Output | 12 shot-level motion instructions | Yes |
| Output | Structured JSON, progress state, and QA reports | Yes |

Outputs are written locally under `runs/brand-ugc/<run-name>/`. Runtime outputs and
delivery bundles are intentionally ignored by Git.

## How it works

The workflow runs seven controlled stages:

1. **Analyze the reference video** — create a local muted proxy of at most 720p and,
   when present, a mono audio track for multimodal analysis.
2. **Build the reference board** — extract 12 frames from the original video locally.
3. **Rewrite the shot script** — adapt the creative to the supplied product, person,
   copy, and verified facts.
4. **Write 12 image prompts** — lock composition, product appearance, character, and
   continuity across shots.
5. **Generate the template storyboard** — render one 2K board and run visual QA.
6. **Generate the final storyboard** — integrate the product and optional person,
   then run visual QA again.
7. **Write the video prompt** — produce one Seedance master prompt plus 12 detailed
   motion instructions.

Every structured stage is validated against JSON Schema. Schema repair and image
regeneration are each limited to one retry.

## Privacy, cost, and quality safeguards

- The original reference video stays local. Only a derived muted analysis proxy and
  optional mono audio track are sent for analysis.
- Product and optional person images are sent to EvoLink only when required by the
  generation workflow.
- Logs must not contain API keys, authorization headers, Base64 payloads, or temporary
  resource URLs.
- The workflow checks EvoLink balance before paid generation.
- A run is capped at 14 model business requests.
- `2K` is the default. The workflow never silently downgrades to `1K`.
- Missing product facts remain unverified; the workflow must not invent claims.
- If an image fails QA twice, the run stops and preserves the report instead of
  passing a failed asset downstream.

## Manual installation

Use this fallback if Node.js is unavailable:

1. Download the repository from
   [GitHub](https://github.com/haonan-c/brand-ugc/archive/refs/heads/main.zip).
2. Extract the archive.
3. Copy both `brand-ugc` and `imagegen-api` into your Codex skills directory.

```text
Windows:      %USERPROFILE%\.codex\skills\
macOS/Linux:  ~/.codex/skills/
```

Restart Codex after copying the folders.

## Advanced CLI usage

The conversational Codex workflow is recommended. For direct pipeline control:

```bash
python ~/.codex/skills/brand-ugc/scripts/run_public_pipeline.py \
  --run-name "my-product-ugc" \
  --video "/absolute/path/reference.mp4" \
  --product-image "/absolute/path/product.png" \
  --person-image "/absolute/path/person.jpg" \
  --copy-file "/absolute/path/copy.txt" \
  --product-info "Verified product facts and constraints" \
  --resolution "2K"
```

Omit optional arguments when you do not have those inputs. If a run is interrupted,
repeat the same command with `--resume`. Existing task IDs are polled rather than
submitted again.

## Development

Run the test suite from the repository root:

```bash
PYTHONPATH=. uv run --with pytest pytest -q
```

Repository layout:

```text
brand-ugc/       Main workflow skill
imagegen-api/    EvoLink image-generation adapter
tests/           Contract, state, media, and offline end-to-end tests
test-assets/     Licensed or source-documented test inputs
docs/            API compatibility notes
```

## License

The original project code is available under the [MIT License](LICENSE).

Adapted workflow ideas and controlled vocabularies retain their upstream licenses.
See [`brand-ugc/THIRD_PARTY_NOTICES.md`](brand-ugc/THIRD_PARTY_NOTICES.md) and
[`brand-ugc/licenses/`](brand-ugc/licenses/) for details.
