---
name: image-generator
description: Generate or edit 1K/2K images from prompts, local images, or public image URLs through an image-generation API. The current backend is EvoLink Nano Banana Pro. Use when Codex needs 生图、图生图、图片编辑、gemini-3-pro-image-preview、Nano Banana Pro，或为 ugc-storyboard 生成分镜图并恢复异步任务。
---

# 图片生成

使用 `gemini-3-pro-image-preview` 创建 EvoLink 异步图片任务，轮询结果并立即
下载到本地。当前实现使用 EvoLink，并与 `ugc-storyboard` 一起安装，共用其薄适配器。

## 配置

优先读取：

1. `EVOLINK_API_KEY`
2. 兼容环境变量 `IMAGEGEN_API_KEY`
3. `secrets/api_key.txt`

环境变量名可兼容，密钥内容必须由 EvoLink 签发。不要显示或记录真实密钥。

## 运行

macOS/Linux：

```bash
python3 scripts/generate_image.py \
  --provider nanobanana \
  --prompt-file prompt.txt \
  --image-file reference.png \
  --aspect-ratio 9:16 \
  --resolution 2K \
  --output-dir generated-images
```

Windows PowerShell 使用同一组参数，并把 `python3` 替换为 `python`。

- 固定模型：`gemini-3-pro-image-preview`
- 支持分辨率：`1K`、`2K`
- 默认：`2K`
- 不自动降级
- 提示词按 EvoLink 2000-token 上限进行保守裁剪
- 任务 ID 保存在输出目录 `task.json`
- 重复运行时若已有任务 ID，只轮询和下载，不再次提交

旧 `--provider nanobanana`、`--image-file`、`--image-url`、`--aspect-ratio`、
`--resolution` 和 `--output-dir` 参数继续可用。EvoLink 不支持旧 OSS key
参数；传入 `--osskey` 时明确停止。

详细接口合同见 `references/api.md`。
