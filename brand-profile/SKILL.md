---
name: brand-profile
description: Create, validate, read, and resolve reusable local profiles for multiple brands and products. Use when Codex needs to 建立品牌档案、保存品牌语气和视觉规范、维护已核实产品卖点与证据、管理禁用表达，或为 ugc-storyboard、ugc-image-post 和 ask-brand 提供一次性不写回的品牌上下文。
---

# 品牌档案

把品牌、产品事实和营销约束保存在当前项目的 `.brand_ugc/brands/` 中。

## 核心规则

- 支持多个品牌；每个品牌可以包含多个产品。
- 只把有明确证据的陈述放入 `verified_claims`。
- 任务覆盖只生成临时上下文，不静默改写长期档案。
- 保存已存在的档案时必须显式使用 `--replace`。
- 不显示或保存 API Key、Authorization、Base64 或临时资源 URL。

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
`product`，禁止覆盖品牌或产品 ID。

## 给下游 Skill

向下游传递 `resolve` 输出或品牌 `profile.json` 的绝对路径。单次任务提供的信息
优先于档案；未提供的信息保持未核实，不从产品类别或对标内容推断功效。
