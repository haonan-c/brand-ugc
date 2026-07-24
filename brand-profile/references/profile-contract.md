# 品牌档案合同

## 存储

```text
.brand_ugc/
  brands/
    <brand-id>/
      profile.json
      assets/
      products/
```

`brand-id` 和 `product-id` 只使用小写字母、数字与连字符。

## 字段

- `schema_version`：当前固定为 `1`。
- `brand_id`、`brand_name`：品牌稳定标识与显示名称。
- `audiences`：品牌层目标人群。
- `voice`：语气特征、建议表达和禁用表达。
- `visual`：品牌颜色、字体、Logo 本地路径和圆角设计变量。
- `compliance.prohibited_claims`：任何任务都不得使用的声明。
- `defaults`：默认 CTA 与话题标签。
- `products`：产品数组。

每个产品包含：

- `product_id`、`name`
- `images`：本地产品素材路径
- `verified_claims`：由 `claim` 和非空 `evidence` 组成
- `target_audiences`
- `use_cases`
- `prohibited_expressions`

## 任务覆盖

任务覆盖文件可以包含：

```json
{
  "voice": {"traits": ["温暖", "可信"]},
  "product": {"use_cases": ["晚间护理"]}
}
```

字典递归合并，数组整体替换。解析结果只写到标准输出，不修改 `profile.json`。
