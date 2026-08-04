---
name: setup-brand-ugc
description: Check local dependencies (Python, Node.js, ImageMagick, CJK fonts, FFmpeg/FFprobe), report which brand-ugc Skills are installed, guide first-time EvoLink and TikHub credential setup, and write the brand-ugc guidance block into the project's AGENTS.md or CLAUDE.md. Use when Codex needs to 初始化配置、检查依赖、配置 EvoLink 或 TikHub Key、诊断安装问题、写入项目 AGENTS.md 引导，或帮助第一次使用的用户完成 brand-ugc 首次设置。
---

# brand-ugc First-Time Setup

Run every command below from this Skill's own directory; all relative paths (`scripts/…`) resolve against it.

Guide the user through the first post-install environment check and credential configuration. Do no content production and call no paid API.

## Core rules

- Ask one question at a time; first decide which paths the user needs, then check and guide only the dependencies and credentials that path requires.
- This is an Agent-led initialization flow: actively run the read-only checks and any credential-free, cost-free configuration; do not merely report steps or paste a chain of commands for the user to finish alone.
- Never ask the user to paste a real API key into the chat, a command-line argument, or any input the Agent can read; by default the user fills the project credential file in a trusted editor.
- For missing system dependencies, only report them and give the install command; do not silently install on the user's behalf and do not modify system or security settings.
- Do not overwrite already-configured credentials unless the user explicitly asks to replace them.
- Creating a brand profile is optional and up to the user; finishing setup does not mean a brand profile exists.

## Workflow

### 1. Choose the target path

Ask one question first: is this run for image posts, short video, the topic radar, or all of them? The answer scopes the rest so only the relevant dependencies are checked, avoiding trouble over paths that are not needed.

| Path | Required system dependencies | Required credentials |
| --- | --- | --- |
| Image post (`ugc-image-post`) | ImageMagick, CJK font | EvoLink |
| Short video (`ugc-storyboard`) | FFmpeg, FFprobe | EvoLink |
| Topic radar (`xhs-topic-radar`) | Node.js `>=22.5.0` | TikHub |

### 2. Check dependencies and install status

First have the Agent initialize the project-level credential template; the command never overwrites an existing file:

```bash
python3 scripts/setup_check.py init --project-root "$PWD"
```

The template path is fixed at `<project>/.brand_ugc/credentials.json` and is added to the project `.gitignore` automatically. Then run the check:

```bash
python3 scripts/setup_check.py check --project-root "$PWD"
```

It returns JSON containing the status of `python`/`node`/`imagemagick`/`cjk_font`/`ffmpeg`/`ffprobe`, the install status of the six Skills (`skills`), the EvoLink and TikHub credential status (`credentials`), and the brand profiles already present in the project (`brand_profiles`).

Show only the missing items relevant to the user's chosen path, with the matching command from "Dependency install reference" below. If a Skill is not installed, tell the user to fill the gap with the one-shot install command from the README:

```bash
npx -y skills@latest add haonan-c/brand-ugc \
  --skill ask-brand xhs-topic-radar brand-profile ugc-image-post ugc-storyboard image-generator setup-brand-ugc \
  --agent codex --global --yes
```

### 3. Configure credentials

By default, have the user open `<project>/.brand_ugc/credentials.json` in a trusted editor and fill only what is needed:

```json
{
  "schemaVersion": 1,
  "tikhubApiKey": "",
  "evolinkApiKey": ""
}
```

The user fills only the fields the current path requires. After saving, the Agent re-runs `check`; do not require the user to set an environment variable each time.

EvoLink key resolution order:

1. `EVOLINK_API_KEY`
2. `IMAGEGEN_API_KEY` (legacy compatibility)
3. `evolinkApiKey` in the project's `.brand_ugc/credentials.json`
4. legacy `<install>/image-generator/secrets/api_key.txt`

TikHub key resolution order:

1. `TIKHUB_API_KEY`
2. `tikhubApiKey` in the project's `.brand_ugc/credentials.json`
3. legacy user-level `${XDG_CONFIG_HOME:-~/.config}/pi-xhs-topic-radar/credentials.json`

Environment variables serve as a temporary override in both chains. The key must be issued by the matching provider; never display or log a real key.

**EvoLink (needed for the image-post and short-video paths)**: fill `evolinkApiKey`. If the user prefers not to store the credential in the project, an environment variable still works:

```bash
export EVOLINK_API_KEY="<用户自己的 Key>"
```

**TikHub (needed for the topic-radar path)**: fill `tikhubApiKey`. Do not have the Agent start a hidden-input command or ask the user to type into a terminal; point directly to the absolute path of the project credential file above.

On the user's next message, the Agent re-runs `key status` with the same `--workspace` and this Skill's `check`. If a key has appeared in chat, logs, or a screenshot, it must be revoked and regenerated first and must not be written to the project file.

### 4. Write the project guidance doc

Write the brand-ugc usage guidance into the project's `AGENTS.md` and point `CLAUDE.md` at it, so later sessions need not re-explain these Skills. Preview first:

```bash
python3 scripts/setup_check.py agents-doc --project-root "$PWD" --dry-run
```

Show `block` and `pointer_block` to the user and, after consent, write them (this creates or modifies files in the user's project):

```bash
python3 scripts/setup_check.py agents-doc --project-root "$PWD"
```

The write locations are fixed, so do not ask the user which file:

- `AGENTS.md` carries the full guidance; it is created if absent.
- `CLAUDE.md` holds only an `@AGENTS.md` import block pointing at `AGENTS.md`, created if absent, so Claude Code reads one shared guidance instead of two separately maintained copies.

The blocks in both files are wrapped by `<!-- brand-ugc:start -->` / `<!-- brand-ugc:end -->`; a repeat run updates only the block interior and leaves the user's other sections untouched. When nothing changed, the corresponding file returns `action: "unchanged"` and is not written. If the user wants different wording, they edit the block in the file directly, but the next run of this step will overwrite it.

### 5. Optional: create the first brand profile

If `brand_profiles` is empty, ask whether to create one now. If yes, hand off to `$brand-profile`; do not duplicate the brand-profile field logic in this Skill. If no, skip it — brand info provided within a task can serve as temporary context.

After creating one, this step's step 4 can be re-run so the brand-profile list in the guidance stays current.

### 6. Summary

Have the Agent run `check` once more to confirm status, and give a short summary telling the user: which dependencies are ready, which credentials are configured, which file the guidance was written to, and which original task will resume next. When initialization was triggered by an upstream Skill, resume that task directly instead of asking the user to re-select an entry point.

## Dependency install reference

macOS (Homebrew):

```bash
brew install imagemagick ffmpeg
brew install --cask font-noto-sans-cjk-sc   # 或已安装苹方 / 微软雅黑也可以
```

Node.js (topic radar requires `>=22.5.0`):

```bash
brew install node   # 或使用 nvm install 22
```

Linux (Debian/Ubuntu):

```bash
sudo apt-get install imagemagick ffmpeg fonts-noto-cjk
```

Windows: install [ImageMagick](https://imagemagick.org/script/download.php#windows), [FFmpeg](https://www.gyan.dev/ffmpeg/builds/), and [Node.js](https://nodejs.org/) from their official sites and make sure they are on `PATH`; a CJK font (Microsoft YaHei) usually ships with the system.

After installing, restart the terminal or the Codex session, then re-run the step 2 `check` to confirm.
