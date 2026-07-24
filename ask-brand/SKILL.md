---
name: ask-brand
description: Diagnose a brand marketing request, inspect available local assets, and route it to exactly one brand-profile, ugc-image-post, or ugc-storyboard workflow. Use when users ask broadly for 品牌营销、新品内容、图文还是短视频的选择、营销素材检查、创建品牌档案，或希望从统一入口开始品牌内容生产。
---

# Ask Brand

作为品牌内容生产的统一入口。负责诊断、素材检查和编排，不复制下游 Skill 的生产
逻辑。

## 路由原则

- 用户明确要求图文时，直接进入 `ugc-image-post`。
- 用户明确要求短视频或分镜时，直接进入 `ugc-storyboard`。
- 用户明确要求创建或更新品牌档案时，直接进入 `brand-profile`。
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

## 编排

### `brand-profile`

创建、保存或解析品牌和产品档案。任务覆盖不自动写回长期档案。

### `ugc-image-post`

需要对标图片、对标文案和产品图。负责内容方案确认、图文生成、排版、QA 和恢复。

### `ugc-storyboard`

需要对标视频和产品图。负责十二宫格分镜和 Seedance 提示词。

路由后遵循下游 Skill 的输入、确认点、费用限制和停止条件。最终汇总下游交付物，
但不要由 `ask-brand` 直接调用生图 API 或重写下游状态。
