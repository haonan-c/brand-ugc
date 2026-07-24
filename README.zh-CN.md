<p align="right">
  <a href="README.md">English</a> · <strong>简体中文</strong>
</p>

<p align="center">
  <img src="assets/brand-ugc-workflow.png" alt="品牌 UGC 内容生产工作流" width="100%">
</p>

# brand-ugc

从统一入口诊断品牌营销需求，把对标视频或对标图文迁移为品牌专属内容。

这个仓库包含五个可以组合安装的 Codex Skill：

- `ask-brand`：诊断需求、检查素材并路由到正确工作流。
- `brand-profile`：维护本地多品牌、多产品档案和已核实事实。
- `ugc-image-post`：生成小红书式多图候选稿、文案、预览和 QA。
- `ugc-storyboard`：生成十二宫格短视频分镜和 Seedance 提示词。
- `image-generator`：两个生产工作流共用的 EvoLink 生图适配器。

> [!IMPORTANT]
> 图文路径交付可发布候选稿，但不会自动发布。视频路径交付分镜图和提示词，不直接
> 渲染最终 MP4。

## 快速开始

### 1. 运行条件

- [Codex](https://openai.com/codex/)
- Node.js 与 `npx`，只用于一键安装
- Python 3.10 或更高版本
- 图文路径：ImageMagick，以及 Noto Sans CJK SC、苹方或微软雅黑字体
- 视频路径：FFmpeg 和 FFprobe
- 在线生图：[EvoLink API Key](https://evolink.ai/dashboard/keys)

macOS/Linux 可以先确认：

```bash
python3 --version
magick -version
ffmpeg -version
ffprobe -version
```

### 2. 一条命令安装全部 Skill

```bash
npx -y skills@latest add haonan-c/brand-ugc \
  --skill ask-brand brand-profile ugc-image-post ugc-storyboard image-generator \
  --agent codex --global --yes
```

安装后完全退出并重启 Codex，或新建一个任务。确认安装：

```bash
npx -y skills@latest list --global --agent codex
```

### 3. 配置 EvoLink

推荐设置：

```bash
export EVOLINK_API_KEY="<YOUR_EVOLINK_KEY>"
```

也可以把 Key 单独保存在：

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
| 图文 | 1–9 张对标图片、对标文案、产品图 | 4–9 张 3:4 图片、三个标题、正文、预览、JSON、QA |
| 视频 | 对标视频、产品图 | 2K 十二宫格、Seedance 总提示词、12 条运动指令、QA |
| 品牌档案 | 品牌 ID、品牌名称、产品数组 | 可复用的 `profile.json` 和任务上下文 |

人物图、品牌档案和额外产品事实都是可选输入。

## 隐私、费用和质量保护

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

## 开发测试

```bash
PYTHONPATH=. uv run --with pytest pytest -q
```

仓库结构：

```text
ask-brand/        统一诊断与编排入口
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
