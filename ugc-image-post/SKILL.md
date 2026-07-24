---
name: ugc-image-post
description: Analyze one benchmark image post and its copy, then create a branded Xiaohongshu-style multi-image publishable candidate from product assets and optional brand profile. Use when Codex needs 对标图文分析、结构级创意迁移、小红书封面与内页组图、产品图锁定、中文确定性排版、标题正文生成、图文视觉QA或继续中断的图文任务。
---

# UGC 图文生成

把一组有顺序的对标图片、对标文案和产品图转换为品牌专属的图文候选稿。默认生成
六张 3:4 图片、三个标题候选、正文、话题标签、整组预览和 QA 报告。

## 运行条件

- Python 3.10 或更高版本
- ImageMagick 的 `magick` 命令
- `image-generator` 与 `ugc-storyboard` Skill
- 在线生成时配置 EvoLink API Key
- 支持中文的 Noto Sans CJK SC、苹方或微软雅黑字体

## 输入边界

- 对标图片：必填，1–9 张本地文件，保持原顺序。
- 对标文案：必填，本地文本文件。
- 产品图：必填，至少一张清晰图片；透明背景 PNG 的合成效果最佳。
- 品牌档案：选填，来自 `brand-profile`。
- v1 每次只分析一个对标笔记，不抓取平台链接，不融合多个笔记。

只迁移钩子、叙事、页面功能、信息层级和视觉规律。重写全部文案，不复制平台 UI、
头像、水印、原作者人物、商标、插画或高度识别性的设计。

## 1. 生成内容方案

按顺序检查对标图片和文案，读取 `references/content-plan-contract.md`，再按照
`schemas/content-plan.schema.json` 写入内容方案。

- 默认六页；用户可以指定 4–9 页。
- 恰好生成三个标题候选，只选择一个进入视觉生产。
- 每项事实记录来源和证据。
- 品牌档案决定表达；对标内容只提供方法。
- 真实产品合成使用 `real_composite`；只有必须交互时使用 `ai_interaction`。
- 版式只能从 `references/layouts.md` 的受控组件中选择。

建议把草案保存到 `.brand_ugc/drafts/<run-name>/content-plan.json`。

## 2. 固化输入并等待确认

```bash
python3 scripts/run_pipeline.py \
  --run-name "<run-name>" \
  --reference-image "/absolute/path/reference-01.png" \
  --reference-image "/absolute/path/reference-02.png" \
  --reference-copy-file "/absolute/path/reference-copy.txt" \
  --product-image "/absolute/path/product.png" \
  --plan-file "/absolute/path/content-plan.json" \
  --brand-profile-file "/absolute/path/profile.json" \
  --product-id "<product-id>" \
  --resolution "2K"
```

没有品牌档案时省略对应参数。首次运行输出 `awaiting_approval`，只保存输入和
`outputs/内容方案.md`，不调用生图 API。向用户展示方案并等待确认。

## 3. 生成并排版

确认后使用完全相同的参数，再添加：

```text
--approve --resume
```

- 在线生图只创建无字底图；真实产品像素由本地 SVG 排版合成。
- `ai_interaction` 页面把产品图作为生图参考，并要求严格视觉 QA。
- 中文、Logo 和营销文字不交给生图模型绘制。
- 2K 是默认值；只有用户明确接受时才传 `--resolution 1K`。
- 每页基础生成一次；全组最多追加两次页面纠错，同一页最多纠错一次。
- 恢复任务复用已存在的图片和任务目录，不重复提交。

开发和演示时可传 `--offline`，使用本地对标图作为底图，不调用付费 API。

## 4. 视觉 QA

在线生成返回 `awaiting_visual_qa` 后，读取
`references/visual-qa-contract.md`，检查所有页面并写出符合
`schemas/visual-qa.schema.json` 的报告。

重新运行并添加：

```text
--visual-qa-file "/absolute/path/visual-qa.json" --approve --resume
```

失败报告最多触发两页纠错，纠错图仍需再次审核。通过报告才把在线任务标记为
`completed`。三页及以上存在重大问题时停止自动纠错。

## 最终交付

面向用户的文件位于 `.brand_ugc/<run-name>/deliverables/`：

- `page-01.png` 至最后一页
- `整组预览.png`
- `发布文案.md`
- `图文内容.json`
- `QA报告.json`

最终回复直接显示整组预览，并给出发布文案与交付目录。不要自动发布到平台。
