---
name: ugc-storyboard
description: Generate a final 12-panel brand UGC storyboard image and a production-ready 15-second Seedance prompt from a benchmark video, product image, optional person image, copy, product notes, and optional brand profile. Use when Codex needs to analyze or adapt a 品牌 UGC 短视频、生成十二宫格分镜、替换商品或人物、应用品牌档案、运行 EvoLink 多模态分析和生图流程，或继续一个中断的分镜任务。
---

# UGC 分镜生成

运行七阶段品牌 UGC 视频改编流程，最终交付十二宫格分镜图和 Seedance 视频提示词，
不生成最终 MP4。

## 首次配置

1. 从 `https://evolink.ai/dashboard/keys` 获取一个 EvoLink API Key。
2. 优先设置环境变量 `EVOLINK_API_KEY`。
3. 也可把密钥写入与本 Skill 同级安装的
   `image-generator/secrets/api_key.txt`；一键全局安装的默认位置是
   `~/.agents/skills/image-generator/secrets/api_key.txt`。
4. 兼容读取旧环境变量名 `IMAGEGEN_API_KEY`，但其中必须是 EvoLink 密钥。
5. 不在聊天、日志或提示词中显示密钥。
6. 确认本机已安装 Python 3.10 或更高版本、FFmpeg 和 FFprobe。

## 输入

- 对标视频：必填，只在本地保存并用于抽帧。
- 产品图：必填。
- 人物图：选填；提供时锁定人物一致性。
- 文案文件：选填。
- 产品信息：建议提供，只使用用户文字和产品图中直接可见的事实。
- 品牌档案：选填；补充品牌语气、视觉约束、已核实事实和禁用表达。

## 运行

macOS/Linux：

```bash
python3 ~/.agents/skills/ugc-storyboard/scripts/run_public_pipeline.py \
  --run-name "<run_name>" \
  --video "<benchmark_video.mp4>" \
  --product-image "<product.png>" \
  --person-image "<optional_person.jpg>" \
  --copy-file "<optional_copy.txt>" \
  --brand-profile-file "<optional_brand_profile.json>" \
  --brand-product-id "<optional_product_id>" \
  --product-info "<产品名称、可验证卖点和限制>" \
  --resolution "2K"
```

Windows PowerShell：

```powershell
python "$env:USERPROFILE\.agents\skills\ugc-storyboard\scripts\run_public_pipeline.py" `
  --run-name "<run_name>" `
  --video "<benchmark_video.mp4>" `
  --product-image "<product.png>" `
  --person-image "<optional_person.jpg>" `
  --copy-file "<optional_copy.txt>" `
  --brand-profile-file "<optional_brand_profile.json>" `
  --brand-product-id "<optional_product_id>" `
  --product-info "<产品名称、可验证卖点和限制>" `
  --resolution "2K"
```

同名运行已存在时不要覆盖。显式添加 `--resume` 后，仅继续未完成阶段；
已有 EvoLink 图片任务 ID 时只轮询，不重新提交。

品牌档案只有一个产品时可以省略 `--brand-product-id`。未提供品牌档案时行为与
原流程完全一致；提供档案时，本次产品信息优先，档案补充长期约束但不会被写回。

默认把任务的全部数据保存在当前项目的 `.brand_ugc/<run_name>/`，包括输入副本、
中间产物、生成结果、QA、进度和断点状态。不要在该目录之外创建品牌 UGC 任务
产物。只有用户显式指定其他位置时才传入 `--output-root`。

`2K` 是默认质量。只有用户明确接受较低质量时才使用 `--resolution 1K`；
禁止自动从 2K 降级。

## 七阶段

1. 视频解析：本地生成最高 720p 无声代理和单声道音轨，原视频不上传；
   输出 `outputs/12镜头解析.json` 和 `outputs/12镜头解析.md`。
2. 12宫格参考图：从原视频本地抽取 12 帧，输出
   `collages/12宫格参考图.jpg`。
3. 新分镜脚本：输出 JSON 真源和
   `outputs/新产品-12分镜脚本.md`。
4. 12分镜提示词：输出 JSON 真源和
   `outputs/1-12分镜提示词.md`。
5. 第一步模板图：生成 2K 十二宫格并执行视觉 QA；最多纠错生成一次。
6. 最终分镜图：融合产品和可选人物并执行视觉 QA；最多纠错生成一次。
7. 视频提示词：输出一个可直接使用的 15 秒 Seedance 总提示词和
   12 条逐镜头运动指令到 `outputs/视频提示词1-12.txt`。

流程完成后，把最终十二宫格分镜图、完整视频提示词和最终 QA 报告汇总到
`deliverables/`。如果需要在流水线之外补充报告或整理文件，也必须保存在同一
任务目录中；面向用户的最终文件放入 `deliverables/`。

保持用户可见进度词不变：

`视频解析完成`、`12宫格参考图完成`、`新分镜脚本完成`、
`12分镜提示词完成`、`第一步模板图完成`、`最终分镜图完成`、
`视频提示词完成`。

## 合同与停止条件

- 内部 JSON 是唯一数据源；Markdown/TXT 只由通过 Schema 的 JSON 渲染。
- 每个结构化阶段必须恰好包含 12 个连续、无重叠镜头。
- Schema 失败只自动修复一次，第二次失败停止。
- 每个图片阶段 QA 失败只纠错生成一次，第二次失败保留图片和报告并停止。
- 单次运行最多使用配置中的 14 次模型业务请求；达到上限停止。
- 运行前检查 EvoLink 余额。
- 日志不得包含密钥、Authorization、Base64 或临时资源 URL。

在修改阶段规则前，读取 `references/prompt-contract.md`。只在需要执行对应
阶段时读取 `references/stages/` 中相应模块。

## 最终回复

成功后，在聊天中直接发送：

```markdown
![最终12宫格分镜图](/absolute/path/to/.brand_ugc/<run_name>/deliverables/最终12宫格分镜图.png)

视频提示词：
<完整总提示词>
```

同时说明 12 条详细运动指令保存在
`.brand_ugc/<run_name>/deliverables/视频提示词1-12.txt`。
