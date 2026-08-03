---
name: brand-profile
description: Create, validate, read, and resolve reusable local profiles for multiple brands and products, and accumulate consumer insights from interviews, local assets, and topic-radar feedback. Use when Codex needs to 建立品牌档案、保存品牌语气和视觉规范、维护已核实产品卖点与证据、管理禁用表达、沉淀人群痛点与真实用户语言、把选题与评论回流到品牌上下文，或为 ugc-storyboard、ugc-image-post 和 ask-brand 提供一次性不写回的品牌上下文。
---

# 品牌档案

把品牌、产品事实和营销约束保存在当前项目的 `.brand_ugc/brands/` 中。

## 核心规则

- 支持多个品牌；每个品牌可以包含多个产品。
- 只把有明确证据的陈述放入 `verified_claims`。
- 任务覆盖只生成临时上下文，不静默改写长期档案。
- 保存已存在的档案时必须显式使用 `--replace`。
- 不显示或保存 API Key、Authorization、Base64 或临时资源 URL。
- 稳定的品牌事实存 `profile.json`，持续演进的消费者洞察存 `insights.json`。

完整字段说明见 `references/profile-contract.md`。创建或修改档案时按
`schemas/brand-profile.schema.json` 组织 JSON。

## 保存档案

```bash
python3 scripts/manage_profile.py save \
  --profile-file "/absolute/path/to/profile.json" \
  --output-root ".brand_ugc"
```

明确替换已有档案时添加 `--replace`。

## 读取档案

```bash
python3 scripts/manage_profile.py show \
  --brand-id "<brand-id>" \
  --output-root ".brand_ugc"
```

## 生成任务上下文

品牌只有一个产品时可省略 `--product-id`；存在多个产品时必须指定。

```bash
python3 scripts/manage_profile.py resolve \
  --brand-id "<brand-id>" \
  --product-id "<product-id>" \
  --overrides-file "/absolute/path/to/task-overrides.json" \
  --output-root ".brand_ugc"
```

允许覆盖 `audiences`、`voice`、`visual`、`compliance`、`defaults` 和
`product`，禁止覆盖品牌或产品 ID。存在 `insights.json` 时，结果附带按当前产品
过滤后的 `insights`，任务覆盖不能修改它。

## 沉淀消费者洞察

洞察来自三个通道：运营访谈 `interview`、本地素材 `local_asset`、平台回流
`platform_radar`。三者都先产出补丁，向用户展示将要新增和更新的条目，确认后再
合并；不自动写回。

按 `schemas/brand-insights-patch.schema.json` 组织补丁，规则见
`references/insights-contract.md`。运营访谈按 `references/interview-guide.md`
提问，一次只问一个问题；本地素材按 `references/intake-guide.md` 提炼；平台回流
由 `xhs-topic-radar` 在报告完成后产出补丁。

```bash
python3 scripts/manage_profile.py insights-merge \
  --brand-id "<brand-id>" \
  --patch-file "/absolute/path/to/insights-patch.json" \
  --output-root ".brand_ugc"
```

```bash
python3 scripts/manage_profile.py insights-show \
  --brand-id "<brand-id>" \
  --output-root ".brand_ugc"
```

同一条洞察被**不同**观察重复命中会累加 `observed_count` 并提升 `confidence`，
所以多次合并是预期行为，不是错误；但 `source`、`observed_at` 和 `ref` 完全相同
的观察只计一次，误跑两次同一份补丁不会抬高置信度。`platform_radar` 反映品类需求
而非本品牌评价，不能写入
`differentiation`。回流平台内容时只保留归纳表述和短语级原话，不保存评论原文和
作者标识。

## 给下游 Skill

向下游传递 `resolve` 输出或品牌 `profile.json` 的绝对路径。单次任务提供的信息
优先于档案；未提供的信息保持未核实，不从产品类别或对标内容推断功效。
