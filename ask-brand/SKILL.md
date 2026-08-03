---
name: ask-brand
description: Diagnose a brand marketing request, inspect available local assets, and route it to exactly one xhs-topic-radar, brand-profile, ugc-image-post, or ugc-storyboard workflow. Use when users ask broadly for 小红书选题研究、品牌营销、新品内容、图文还是短视频的选择、营销素材检查、创建品牌档案，或希望从统一入口开始品牌内容生产。
---

# Ask Brand

作为品牌内容生产的统一入口。负责诊断、素材检查和编排，不复制下游 Skill 的生产
逻辑。

## 路由原则

- 用户明确要求选题（包括“需要/想要/帮我找某行业的选题”）、选题雷达、每日选题、需求词或话题研究时，直接进入 `xhs-topic-radar`；不要把行业词误解为软件、项目或产品的命名需求。
- 用户明确要求图文时，直接进入 `ugc-image-post`。
- 用户明确要求短视频或分镜时，直接进入 `ugc-storyboard`。
- 用户明确要求创建或更新品牌档案时，直接进入 `brand-profile`。
- 同时要求选题研究与成品生产时，只问一个顺序问题；推荐先做选题，再由用户选择策略卡。
- 需求模糊时给出一个推荐路径，并且一次只问一个关键问题。
- 不默认同时生成图文和视频。
- 没有品牌档案时不强制打断；可以使用单次任务信息继续。
- 品牌档案存在多个品牌或产品且用户未指定时，只询问所需的品牌或产品。

详细规则见 `references/routing-contract.md`。

## 素材诊断

需要可重复检查时运行：

```bash
python3 scripts/route_request.py \
  --request "<用户原始需求>" \
  --reference-image "/absolute/path/reference.png" \
  --reference-copy-file "/absolute/path/copy.txt" \
  --reference-video "/absolute/path/reference.mp4" \
  --product-image "/absolute/path/product.png" \
  --brand-profile-file "/absolute/path/profile.json"
```

按 `schemas/route-decision.schema.json` 读取结果：

- `ready`：直接执行 `recommended_skill`，不要重复确认路径。
- `needs_input`：只询问 `missing_inputs` 中缺少的必填素材。
- `needs_confirmation`：向用户提出 `question`，等待回答后再路由。

## 前置配置编排

`ready` 只表示路由已经明确，不代表下游环境已经就绪。首次进入推荐 Skill 时：

- 先按目标路径调用 `setup-brand-ugc` 创建或复用项目级 `.brand_ugc/credentials.json`，再做只读预检；由 Agent 执行检查和无需凭证、无需付费的初始化，不要只把一组命令丢给用户。
- 缺少凭证时，不要启动 `key set`、隐藏输入或任何等待终端输入的命令，也不要默认建议环境变量。先确保项目凭证模板已创建，再明确提醒用户用可信编辑器打开 `<项目>/.brand_ugc/credentials.json`，只填写当前路径需要的字段。
- 给出凭证文件的绝对路径和字段名：TikHub 使用 `tikhubApiKey`，EvoLink 使用 `evolinkApiKey`。随后停止并等待用户保存；不要读取文件内容、要求用户粘贴 Key、要求用户自行运行状态检查、只回复固定口令或重新描述原需求。
- 用户下一次回复后，由 Agent 自动复查凭证状态并恢复原下游任务。
- 用户说“帮我配置”时，由 Agent 创建模板并定位文件，但真实 Key 必须由用户在可信编辑器中填写；其他可安全自动执行的步骤都由 Agent 完成。
- 如果真实 Key 曾被粘贴到聊天、日志或截图中，不使用也不保存；要求先撤销并生成新 Key，再通过可信编辑器写入项目凭证文件。

初始化是推荐工作流的前置步骤，不算同时启动第二条内容生产路径。

## 编排

### `xhs-topic-radar`

先查询真实搜索联想需求词，在用户明确批准剩余费用后采集笔记与评论，生成带证据和创作结构的策略卡。它不直接生图或发布内容。报告完成后可以询问一次是否把这次的消费者语言回流到品牌洞察。

### `brand-profile`

创建、保存或解析品牌和产品档案，并沉淀来自访谈、本地素材和平台回流的消费者洞察。任务覆盖和洞察都不自动写回长期档案。

### `ugc-image-post`

需要对标图片、对标文案和产品图。负责内容方案确认、图文生成、排版、QA 和恢复。

### `ugc-storyboard`

需要对标视频和产品图。负责十二宫格分镜和 Seedance 提示词。

路由后遵循下游 Skill 的输入、确认点、费用限制和停止条件。最终汇总下游交付物，
但不要由 `ask-brand` 直接调用 TikHub、生图 API 或重写下游状态。完成选题雷达后，只有用户明确选择策略卡并确认内容形式，才能开启独立的图文或视频生产运行。
