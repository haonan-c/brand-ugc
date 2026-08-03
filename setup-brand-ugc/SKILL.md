---
name: setup-brand-ugc
description: Check local dependencies (Python, Node.js, ImageMagick, CJK fonts, FFmpeg/FFprobe), report which brand-ugc Skills are installed, and guide first-time EvoLink and TikHub credential setup. Use when Codex needs to 初始化配置、检查依赖、配置 EvoLink 或 TikHub Key、诊断安装问题，或帮助第一次使用的用户完成 brand-ugc 首次设置。
---

# brand-ugc 初始化设置

引导用户完成安装后的首次环境检查和凭证配置，不做内容生产、不调用付费 API。

## 核心规则

- 一次只问一个问题；先确定用户要用哪些路径，再只检查和引导该路径需要的依赖与凭证。
- 这是 Agent 主导的初始化流程：主动执行只读检查和无需凭证、无需付费的配置，不要只报告步骤或连续粘贴命令让用户自行收尾。
- 从不要求用户把真实 API Key 粘贴进聊天记录或命令参数；写入凭证时始终通过标准输入。
- 缺失的系统依赖只报告和给出安装命令，不代为静默安装、不修改系统或安全配置。
- 已经配置好的凭证不覆盖，除非用户明确要求更换。
- 创建品牌档案是可选步骤，由用户决定是否现在做；setup 完成不等于已经有品牌档案。

## 使用流程

### 1. 选择目标路径

先问一个问题：这次准备用图文、短视频、选题雷达，还是全部？回答决定后续只检查相关依赖，不用为不需要的路径找麻烦。

| 路径 | 需要的系统依赖 | 需要的凭证 |
| --- | --- | --- |
| 图文 (`ugc-image-post`) | ImageMagick、中文字体 | EvoLink |
| 短视频 (`ugc-storyboard`) | FFmpeg、FFprobe | EvoLink |
| 选题雷达 (`xhs-topic-radar`) | Node.js `>=22.5.0` | TikHub |

### 2. 检查依赖与安装状态

先由 Agent 初始化项目级凭证模板；命令不会覆盖已有文件：

```bash
python3 scripts/setup_check.py init --project-root "$PWD"
```

模板路径固定为 `<项目>/.brand_ugc/credentials.json`，并自动加入项目 `.gitignore`。然后执行检查：

```bash
python3 scripts/setup_check.py check --project-root "$PWD"
```

返回 JSON，包含 `python`/`node`/`imagemagick`/`cjk_font`/`ffmpeg`/`ffprobe` 状态、六个 Skill 的安装情况（`skills`）、EvoLink 与 TikHub 凭证状态（`credentials`），以及当前项目已有的品牌档案（`brand_profiles`）。

只展示用户选定路径相关的缺失项，并给出下方"依赖安装参考"里对应的命令。如果某个 Skill 未安装，提示用户使用 README 中的一键安装命令补齐：

```bash
npx -y skills@latest add haonan-c/brand-ugc \
  --skill ask-brand xhs-topic-radar brand-profile ugc-image-post ugc-storyboard image-generator setup-brand-ugc \
  --agent codex --global --yes
```

### 3. 配置凭证

默认让用户在可信编辑器中打开 `<项目>/.brand_ugc/credentials.json`，按需填写：

```json
{
  "schemaVersion": 1,
  "tikhubApiKey": "",
  "evolinkApiKey": ""
}
```

用户只需填写本次路径需要的字段。保存后由 Agent 重新运行 `check`，不要要求每次设置环境变量。环境变量仍作为临时覆盖，读取优先级为：环境变量 → 项目凭证文件 → 旧用户级凭证文件。

**EvoLink（图文、短视频路径需要）**：填写 `evolinkApiKey`。如果用户不希望把凭证保存在项目中，仍可使用环境变量：

```bash
export EVOLINK_API_KEY="<用户自己的 Key>"
```

**TikHub（选题雷达路径需要）**：填写 `tikhubApiKey`。也可继续使用隐藏输入命令，它会更新同一个项目凭证文件：

```bash
node ~/.agents/skills/xhs-topic-radar/scripts/topic_radar.mjs key set --workspace "$PWD"
```

用户下一次回复后，由 Agent 自动运行带同一 `--workspace` 的 `key status` 和本 Skill 的 `check`。若 Key 已出现在聊天、日志或截图中，必须先撤销并生成新 Key，不能写入项目文件。

### 4. 可选：创建第一个品牌档案

如果 `brand_profiles` 为空，问用户是否现在创建。愿意的话交给 `$brand-profile` 完成，不在这个 Skill 里重复品牌档案的字段逻辑。不愿意也可以跳过，任务内提供的品牌信息可以作为临时上下文。

### 5. 总结

由 Agent 再次运行 `check` 确认状态，用一段简短总结告诉用户：哪些依赖已就绪、哪些凭证已配置、接下来将恢复哪个原任务。初始化由上游 Skill 触发时，直接恢复该任务，不要求用户重新选择入口。

## 依赖安装参考

macOS（Homebrew）：

```bash
brew install imagemagick ffmpeg
brew install --cask font-noto-sans-cjk-sc   # 或已安装苹方 / 微软雅黑也可以
```

Node.js（选题雷达需要 `>=22.5.0`）：

```bash
brew install node   # 或使用 nvm install 22
```

Linux（Debian/Ubuntu）：

```bash
sudo apt-get install imagemagick ffmpeg fonts-noto-cjk
```

Windows：从官方站点安装 [ImageMagick](https://imagemagick.org/script/download.php#windows)、[FFmpeg](https://www.gyan.dev/ffmpeg/builds/)、[Node.js](https://nodejs.org/) 并确保加入 `PATH`；中文字体通常已自带微软雅黑。

安装完成后建议重启终端或 Codex 会话，再重新运行第 2 步的 `check` 确认。
