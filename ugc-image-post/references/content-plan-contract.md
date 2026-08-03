# 图文内容方案合同

## 优先级

1. 用户本次明确指令与合规要求
2. 已核实事实
3. 品牌档案
4. 品牌洞察
5. 产品和目标人群
6. 对标内容的结构规律
7. 对标内容的表面视觉风格

## 内容方案

- `title_options`：恰好三个全新标题。
- `selected_title`：必须来自标题候选。
- `hook_basis`：封面钩子所依据的洞察原文，存在品牌洞察时必填。
- `facts_used`：每项包含 `fact`、`source` 和非空 `evidence`。
- `source`：只允许 `brand_profile`、`user_provided`、
  `product_image_visible`。
- `pages`：4–9 页，默认六页，索引连续。
- `fact_refs`：只能引用 `facts_used` 中的事实。

## 品牌洞察

品牌档案同目录存在 `insights.json` 时，任务上下文会带上按当前产品过滤后的
`insights`。

- `hook_basis` 必须逐字等于某条 `audience_insights.pain_points` 或某个
  `content_pillars.pillar`，封面钩子围绕它展开。
- `native_phrases` 是消费者原话，优先用于正文和标题，不要改写成书面语。
- `objections` 用于决定中间页要提前回应哪些顾虑。
- `language_bank.avoid_patterns` 是风格取向，`compliance.prohibited_claims` 是
  合规红线，两者都要避开。
- 洞察是策略，不是事实。不要把 `pain_points` 或 `content_pillars` 写进
  `facts_used`，也不要据此推断功效、成分或用户体验。
- `provenance.confidence` 为 `low` 的条目可以用，但不要作为唯一的内容主线。

产品资料不足时可以生成中性内容；不要推断功效、成分、认证、销量或用户体验。

## 页面

每页需要：

- 页面功能 `role`
- 受控版式 `layout`
- 图片内 `headline`、`body` 和 `emphasis`
- 不含营销文字的 `visual_prompt`
- `product_mode`
- 使用的 `fact_refs`

`product_mode`：

- `real_composite`：真实产品图由本地排版器合成。
- `ai_interaction`：仅用于手持或使用中的交互场景。
- `none`：页面不展示产品。

封面必须承担钩子，最后一页承担总结、互动或 CTA；中间页面按对标结构和产品事实
决定，不强制使用固定脚本。
