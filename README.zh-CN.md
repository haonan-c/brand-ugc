<p align="right">
  <a href="README.md">English</a> · <strong>简体中文</strong>
</p>

<p align="center">
  <img src="assets/brand-ugc-workflow.png" alt="品牌 UGC 内容生产工作流" width="100%">
</p>

# brand-ugc

从统一入口诊断品牌营销需求，把对标视频或对标图文迁移为品牌专属内容。

这个仓库包含七个可以组合安装的 Agent Skill，Codex 和 Claude Code 都可以直接使用：

- `setup-brand-ugc`：检查本地依赖、已安装 Skill 和凭证状态，引导完成首次设置。
- `ask-brand`：诊断需求、检查素材并路由到正确工作流。
- `xhs-topic-radar`：发现小红书需求语言，生成带证据的每日选题策略卡。
- `brand-profile`：维护本地多品牌、多产品档案和已核实事实。
- `ugc-image-post`：生成小红书式多图候选稿、文案、预览和 QA。
- `ugc-storyboard`：生成十二宫格短视频分镜和 Seedance 提示词。
- `image-generator`：两个生产工作流共用的 EvoLink 生图适配器。

> [!IMPORTANT]
> 图文路径交付可发布候选稿，但不会自动发布。视频路径交付分镜图和提示词，不直接
> 渲染最终 MP4。

## 它如何工作

这套工具没有把所有职责塞进一个大 Skill，而是把“判断做什么”“保存品牌事实”
“生产内容”和“调用生图服务”分开。这样既可以从统一入口开始，也可以在目标明确时
直接调用生产 Skill。

```mermaid
flowchart LR
    U["营销需求与本地素材"] --> A["ask-brand<br/>诊断与路由"]
    A --> T["xhs-topic-radar<br/>需求与选题研究"]
    A --> P["brand-profile<br/>建立或解析品牌档案"]
    A --> I["ugc-image-post<br/>图文生产"]
    A --> V["ugc-storyboard<br/>视频分镜"]
    T --> S["用户选中的策略卡"]
    S -. "独立确认后的生产任务" .-> I
    S -. "独立确认后的生产任务" .-> V
    P -. "品牌约束与已核实事实" .-> I
    P -. "品牌约束与已核实事实" .-> V
    I --> G["image-generator<br/>共享生图能力"]
    V --> G
    I --> DI["图文候选稿 + QA"]
    V --> DV["十二宫格 + Seedance 提示词"]
```

| 类型 | Skill | 什么时候使用 |
| --- | --- | --- |
| 初始化 | `setup-brand-ugc` | 第一次安装后运行，检查依赖并配置 EvoLink、TikHub 凭证 |
| 统一入口 | `ask-brand` | 需求还比较宽泛、素材不确定，或需要判断先研究、做图文还是视频 |
| 研究入口 | `xhs-topic-radar` | 发现需求词并生成带证据的小红书选题策略卡 |
| 品牌上下文 | `brand-profile` | 创建、更新或选择可复用的品牌与产品事实 |
| 生产入口 | `ugc-image-post` | 已明确要做对标图文迁移 |
| 生产入口 | `ugc-storyboard` | 已明确要做对标视频分镜 |
| 共享能力 | `image-generator` | 由生产 Skill 调用；日常通常不需要直接使用 |

设计原则很简单：一次只选择一条生产路径；付费生图前必须确认内容方案；事实必须
可追溯；所有中间状态保存在本地，任务可以恢复。

## 快速开始

### 1. 运行条件

- [Codex](https://openai.com/codex/) 或 [Claude Code](https://code.claude.com/)；
  评估阶段的 Pi Agent 路径需要 `@earendil-works/pi-coding-agent`
- Node.js 与 `npx`；选题雷达要求 Node.js `>=22.5.0`，其他路径只在一键安装时使用 Node
- Python 3.10 或更高版本
- 图文路径：ImageMagick，以及 Noto Sans CJK SC、苹方或微软雅黑字体
- 视频路径：FFmpeg 和 FFprobe
- 选题雷达：用户自己的 [TikHub API Key](https://api.tikhub.io/)
- 在线生图：[EvoLink API Key](https://evolink.ai/dashboard/keys)

macOS/Linux 可以先确认：

```bash
python3 --version
magick -version
ffmpeg -version
ffprobe -version
```

### 2. 一条命令安装全部 Skill

根据你使用的 Agent 选择对应命令。

**Codex**

```bash
npx -y skills@latest add haonan-c/brand-ugc \
  --skill setup-brand-ugc ask-brand xhs-topic-radar brand-profile ugc-image-post ugc-storyboard image-generator \
  --agent codex --global --yes
```

安装后完全退出并重启 Codex，或新建一个任务。确认安装：

```bash
npx -y skills@latest list --global --agent codex
```

**Claude Code**

```bash
npx -y skills@latest add haonan-c/brand-ugc \
  --skill setup-brand-ugc ask-brand xhs-topic-radar brand-profile ugc-image-post ugc-storyboard image-generator \
  --agent claude-code --global --yes
```

新建一个 Claude Code 会话，然后确认安装：

```bash
npx -y skills@latest list --global --agent claude-code
```

**Pi Agent**（评估阶段，详见 [`docs/pi-agent-driver-evaluation.md`](docs/pi-agent-driver-evaluation.md)）

```bash
npm install -g @earendil-works/pi-coding-agent@0.82.1
npx -y skills@latest add haonan-c/brand-ugc \
  --skill setup-brand-ugc ask-brand xhs-topic-radar brand-profile ugc-image-post ugc-storyboard image-generator \
  --agent pi --global --yes
```

确认安装：

```bash
npx -y skills@latest list --global --agent pi
```

请锁定上面这个 `pi-coding-agent` 版本号，不要用 `@latest`——评估文档里的兼容性结论
是基于这个版本得出的，包本身还是 `0.x`。Pi 目前是作为 brand-ugc 自有运营工作台的
底层 Agent Driver 在评估（见
[ADR 0003](docs/adr/0003-pi-agent-is-the-autonomous-controller.md)），还不是正式的
生产安装方式，请当作 PoC 路径，不是默认推荐。

去掉上面任意命令里的 `--global`，可以只安装到当前项目（Claude Code 写入
`.claude/skills/`，Pi 写入 `.pi/skills/`），而不是用户级目录。三种 Agent 使用的
SKILL.md 完全一致，不需要做任何改动。

> 在 Claude Code 里，Skill 会根据 `description` 自动匹配，所以你可以直接用自然语言
> 描述任务，或者说"使用 ask-brand 这个 skill"。Pi 同样不保证每次都会自动读取完整的
> Skill 内容；需要明确触发某个 Skill 时，用 `/skill:ask-brand` 这类写法显式调用。
> 下文示例里的 `$skill-name` 写法是 Codex 自己的调用语法。

### 3. 运行初始化设置

推荐直接使用 `$setup-brand-ugc`：它会自动检查 Python、Node.js、ImageMagick、中文字体、
FFmpeg/FFprobe 是否齐全，列出缺失依赖对应的安装命令，并引导配置 EvoLink 和 TikHub Key，
不需要自己逐条对照文档。

初始化会在当前项目创建 `.brand_ugc/credentials.json`，该文件已加入 `.gitignore`。在可信编辑器中填写一次即可：

```json
{
  "schemaVersion": 1,
  "tikhubApiKey": "<YOUR_TIKHUB_KEY>",
  "evolinkApiKey": "<YOUR_EVOLINK_KEY>"
}
```

环境变量仍可作为临时覆盖，旧的用户级凭证位置也继续兼容：

```text
Windows:      %USERPROFILE%\.agents\skills\image-generator\secrets\api_key.txt
macOS/Linux:  ~/.agents/skills/image-generator/secrets/api_key.txt
```

不要把真实 Key 发到聊天、截图、日志或 Git 中。

### 4. 从统一入口开始

```text
请使用 $ask-brand 帮我判断这批新品素材更适合先做图文还是短视频，并继续执行推荐路径。

我已上传：
1. 产品图
2. 对标图片和文案（如果有）
3. 对标视频（如果有）
4. 品牌档案（如果有）
```

需求明确时也可以直接使用下面的生产 Skill。

## 推荐使用流程

### 第一次使用

1. 安装七个 Skill，运行 `$setup-brand-ugc` 检查目标路径所需的本地依赖。
2. 用 `$setup-brand-ugc` 引导配置 TikHub Key（选题研究）和 EvoLink Key（在线生图）；仅离线演示图文流程时可以暂不配置 EvoLink。
3. 可选：用 `$brand-profile` 建立品牌语气、禁用表达、产品事实和证据。
4. 整理一组任务素材。图文和视频对标素材不要混在一次生产任务里。
5. 不确定路径时从 `$ask-brand` 开始；目标明确时直接调用生产 Skill。

### 每次内容生产

1. **诊断**：确认目标格式、品牌或产品、必填素材和缺失信息。
2. **规划**：分析对标内容的方法，生成品牌化内容方案，不复制原作品。
3. **确认**：先让用户检查页面结构、文案方向和事实，再允许付费生成。
4. **生产**：生成底图、合成真实产品和文字，或生成十二宫格视频分镜。
5. **质检**：检查事实、品牌一致性、画面完整性和整组连贯性；必要时限次纠错。
6. **交付**：把发布候选、结构化数据、预览和 QA 报告保存到本地。

图文在线任务的状态如下：

| 状态 | 含义 | 下一步 |
| --- | --- | --- |
| `awaiting_approval` | 内容方案已保存，尚未调用生图 API | 确认方案后以 `--approve --resume` 继续 |
| `awaiting_visual_qa` | 已完成在线生成和本地排版 | 检查全部页面并提交视觉 QA |
| `completed` | 视觉 QA 通过，交付物已收集 | 从 `deliverables/` 取用结果 |

如果命令返回错误，先修正输入、依赖或生成问题；输入未改变时可恢复原任务，输入已经
改变时应新建任务。

## 初始化设置

第一次安装或更换电脑后，使用 `$setup-brand-ugc`：

```text
请使用 $setup-brand-ugc 帮我检查依赖并配置这次要用的凭证。

这次准备使用：图文（或短视频 / 选题雷达 / 全部）。
```

它不生成内容、不调用付费 API：先问清楚这次要用哪条路径，再主动检查该路径需要的
系统依赖、报告六个 Skill 的安装状态，并创建项目级 `.brand_ugc/credentials.json`。用户
在可信编辑器中填写所需 Key 一次，随后由 Agent 自动验证并恢复原任务；不需要每次设置
环境变量。全程不会要求把真实 Key 粘贴进聊天记录。

## 选题雷达路径

需要先研究方向再创作时，使用 `$xhs-topic-radar`。它先询问行业和回看周期，只执行受限的搜索联想预览，并在采集笔记与评论前等待用户明确确认。默认软著运行最多 27 次 TikHub 业务请求，费用硬上限为 US$0.30。

每张策略卡包含目标人群、场景、样本内依据、具体证据解读、原样小红书来源链接、搜索联想需求词、标题与写作框架、开头钩子、提纲、CTA、六维加权评分和政策/表述风控。报告保存在 `.brand_ugc/topic-radar/reports/`。

单次搜索快照不代表精确搜索量或全平台趋势，小红书帖子也不是政策权威。报告完成后，由用户先选中一张策略卡，再开启独立的图文或分镜生产任务。

CLI、凭据、费用保护和本地状态说明见 [`docs/xhs-topic-radar.md`](docs/xhs-topic-radar.md)。

## 图文路径

上传一组有顺序的对标图片、对应文案和产品图：

```text
请使用 $ugc-image-post 生成一套小红书式品牌图文候选稿。

只做结构级创意迁移，不复刻原文、人物、商标、水印或平台 UI。
默认生成六张 3:4 图片和三个标题候选。
只使用我提供或产品图中直接可见的事实。
先展示内容方案，等我确认后再生图。
```

默认流程：

1. 分析一个对标笔记的钩子、页面功能、叙事和视觉规律。
2. 生成 4–9 页内容方案，默认六页。
3. 等待用户确认后生成无字底图。
4. 用真实产品图和本地 SVG 完成中文、Logo 与版式合成。
5. 执行整组 QA；最多纠错两页，每页最多一次。
6. 输出独立图片、整组预览、发布文案、结构化内容和 QA。

在线任务初次生成后需要视觉 QA 才能标记完成。全部任务数据保存在
`.brand_ugc/<run-name>/`，交付物位于 `deliverables/`。

## 短视频路径

上传对标视频和产品图：

```text
请使用 $ugc-storyboard 生成一个 15 秒品牌 UGC 分镜。

默认生成 2K 十二宫格分镜和完整 Seedance 提示词。
不要添加未经证实的卖点、字幕、水印或平台 UI。
```

视频路径继续使用七个受控阶段：视频解析、本地抽帧、新脚本、十二条生图提示词、
模板分镜、最终分镜和视频提示词。每个结构化阶段通过 JSON Schema 校验，图片
纠错最多一次。

## 品牌档案

`brand-profile` 把品牌语气、颜色、字体、Logo、禁用表达和产品事实保存在：

```text
.brand_ugc/brands/<brand-id>/profile.json
```

支持多个品牌和多个产品。任务信息可以临时覆盖档案，但不会静默写回。每条
`verified_claims` 必须同时包含声明和证据。

## 输入与输出

| 路径 | 必填输入 | 主要输出 |
| --- | --- | --- |
| 选题雷达 | 行业、回看周期、TikHub Key、明确的采集确认 | 10 张证据策略卡、Markdown/JSON 报告、本地证据包 |
| 图文 | 1–9 张对标图片、对标文案、产品图 | 4–9 张 3:4 图片、三个标题、正文、预览、JSON、QA |
| 视频 | 对标视频、产品图 | 2K 十二宫格、Seedance 总提示词、12 条运动指令、QA |
| 品牌档案 | 品牌 ID、品牌名称、产品数组 | 可复用的 `profile.json` 和任务上下文 |

人物图、品牌档案和额外产品事实都是可选输入。

## 隐私、费用和质量保护

- 选题雷达先执行三次搜索联想预览，剩余 TikHub 采集必须获得明确确认。
- 选题证据和报告保存在本地，原样保留笔记 URL 以便追溯。
- 原始视频保存在本地，只发送最高 720p 的派生分析代理和可选单声道音轨。
- 图文对标图片不直接作为在线生图参考；只有交互页面需要时才发送产品参考图。
- 日志不得包含 API Key、Authorization、Base64 或临时资源 URL。
- 2K 是默认质量，不会静默降级。
- 图文默认六次基础生图，整组最多追加两次页面纠错。
- 视频单次运行最多使用配置中的 14 次模型业务请求。
- 缺失产品信息保持未核实，不虚构功效、成分、认证、销量或体验。

## 高级 CLI

图文路径由 Codex 先生成符合 Schema 的内容方案，再运行：

```bash
python3 ~/.agents/skills/ugc-image-post/scripts/run_pipeline.py \
  --run-name "my-product-post" \
  --reference-image "/absolute/path/reference-01.png" \
  --reference-copy-file "/absolute/path/reference-copy.txt" \
  --product-image "/absolute/path/product.png" \
  --plan-file "/absolute/path/content-plan.json"
```

首次运行只等待确认。确认后使用相同命令添加 `--approve --resume`。

在线生成结束后，Codex 会检查全部页面并生成视觉 QA 文件。再以相同命令追加：

```text
--visual-qa-file "/absolute/path/visual-qa.json" --approve --resume
```

如果任务中断，保留相同的 `--run-name` 和原始输入，使用 `--resume` 继续。需要更换
对标素材、产品或内容方案时，应使用新的任务名，避免把两次任务的状态混在一起。

视频路径：

```bash
python3 ~/.agents/skills/ugc-storyboard/scripts/run_public_pipeline.py \
  --run-name "my-product-ugc" \
  --video "/absolute/path/reference.mp4" \
  --product-image "/absolute/path/product.png" \
  --brand-profile-file "/absolute/path/profile.json" \
  --brand-product-id "<product-id>" \
  --product-info "已核实的产品事实和限制" \
  --resolution "2K"
```

## 本地目录和交付物

```text
.brand_ugc/
├── credentials.json     项目级 TikHub / EvoLink 凭证（已忽略，禁止提交）
├── brands/<brand-id>/profile.json
├── topic-radar/          配置、原始证据、SQLite 历史、证据包和报告
├── drafts/<run-name>/content-plan.json
└── <run-name>/
    ├── inputs/          固化后的输入和清单
    ├── outputs/         内容方案等中间输出
    ├── images/          底图、产品图和排版结果
    ├── state/           运行状态和请求预算
    └── deliverables/    最终图片、文案、JSON、预览和 QA
```

运行目录默认不覆盖其他任务。分享结果时优先发送 `deliverables/`，不要把包含原始
素材、状态或 credentials.json 的整个任务目录上传到公开仓库。

## 常见问题

**为什么运行后没有生图？**

首次运行停在 `awaiting_approval` 是预期行为。它只固化输入并展示内容方案，确认后
才会产生付费请求。

**为什么图片已经生成，任务还没有完成？**

在线任务需要整组视觉 QA。状态为 `awaiting_visual_qa` 时，让 Codex 检查图片并用
视觉 QA 文件恢复任务；只有通过后才进入 `completed`。

**没有品牌档案能否使用？**

可以。任务内提供的品牌信息会作为临时上下文，但不会自动写入长期档案。

**有多个产品时为什么还在询问？**

必须明确选择 `product-id`，防止把不同产品的事实或素材混用。

**中文排版显示方框或 ImageMagick 报错怎么办？**

安装 Noto Sans CJK SC、苹方或微软雅黑字体，并确认 `magick -version` 可以正常
执行。视频解析失败时同样检查 `ffmpeg` 和 `ffprobe`。用 `$setup-brand-ugc` 可以
一次性检查这几项并给出对应安装命令，不用逐条手动确认。

**第一次安装要自己挨个装依赖、配 Key 吗？**

不用手动摸索。安装 Skill 之后先运行 `$setup-brand-ugc`，它会检查依赖、报告缺失
项和安装命令，并引导配置 EvoLink、TikHub 凭证；不需要的路径不会被要求配置。

**可以直接发布到小红书或其他平台吗？**

不可以。当前工作流只生成候选稿和 QA，不包含账号登录、自动发布或平台抓取。

## 开发测试

```bash
PYTHONPATH=. uv run --with pytest pytest -q
```

仓库结构：

```text
setup-brand-ugc/  依赖检查与首次凭证配置引导
ask-brand/        统一诊断与编排入口
xhs-topic-radar/  小红书需求发现与选题策略报告
brand-profile/    多品牌、多产品档案
ugc-image-post/   图文规划、生图、排版、QA 与恢复
ugc-storyboard/   七阶段视频分镜工作流
image-generator/  EvoLink 生图适配器
tests/            合同、CLI、恢复和离线端到端测试
examples/         已授权或记录来源的案例素材
docs/             API 兼容性说明
```

## 许可证

项目原创代码采用 [MIT License](LICENSE)。改编内容继续遵循其上游许可证，详见
[`ugc-storyboard/THIRD_PARTY_NOTICES.md`](ugc-storyboard/THIRD_PARTY_NOTICES.md)。
