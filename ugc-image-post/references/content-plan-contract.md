# 图文内容方案合同

## 优先级

1. 用户本次明确指令与合规要求
2. 已核实事实
3. 品牌档案
4. 产品和目标人群
5. 对标内容的结构规律
6. 对标内容的表面视觉风格

## 内容方案

- `title_options`：恰好三个全新标题。
- `selected_title`：必须来自标题候选。
- `facts_used`：每项包含 `fact`、`source` 和非空 `evidence`。
- `source`：只允许 `brand_profile`、`user_provided`、
  `product_image_visible`。
- `pages`：4–9 页，默认六页，索引连续。
- `fact_refs`：只能引用 `facts_used` 中的事实。

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
