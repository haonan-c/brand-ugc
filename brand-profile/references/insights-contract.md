# 品牌洞察合同

`profile.json` 保存稳定的品牌事实，`insights.json` 保存会持续演进的消费者洞察。
两者并列存放，互不覆盖。

```text
.brand_ugc/brands/<brand-id>/
  profile.json
  insights.json
```

## 事实层与策略层

- 事实层（`profile.json` 的 `verified_claims`）必须有可举证的 `evidence`。
- 策略层（`insights.json`）不要求 `evidence`，但每个条目必须带 `provenance`
  记录来源、观察次数和时间。
- `differentiation` 是例外：它对外是可被质疑的事实性对比，必须有 `evidence`。

## 分区

- `audience_insights`：按人群记录 `pain_points`、`scenarios`、`objections`
  和 `native_phrases`。
- `content_pillars`：品牌可以反复讲的内容方向及其 `angles`。
- `differentiation`：与竞品或品类通行做法的差异点。
- `language_bank`：品牌级的 `voice_samples`、`hook_patterns` 和
  `avoid_patterns`。

条目的 `product_ids` 为空表示品牌级；填写后只在 `resolve` 对应产品时返回。
`product_ids` 必须指向 `profile.json` 中真实存在的产品。

## 采集来源

`source` 只允许三个值：

- `interview`：运营访谈。
- `local_asset`：本地素材（官网文案、详情页、检测报告、客服 FAQ）。
- `platform_radar`：`xhs-topic-radar` 的评论与策略卡回流。

`platform_radar` 反映的是品类需求，不是对本品牌的评价，因此不能写入
`differentiation`。差异化主张必须由品牌自行举证。

## 脱敏

回流平台内容时只提炼归纳后的表述和短语级原话，不整条保存评论原文，不保存作者
昵称、用户 ID、联系方式或站外链接。`ref` 只允许 `run_id`、`note_urls` 和
`note` 三个字段。

## 合并语义

补丁在顶层声明一次 `source`、`observed_at` 和 `ref`，条目本身不携带
`provenance`，由 `insights-merge` 计算。按
`schemas/brand-insights-patch.schema.json` 组织补丁。

同一条目由 key 字段判定：`audience_insights` 用 `audience`，
`content_pillars` 用 `pillar`，`differentiation` 用 `vs` 加 `point`。

命中已有条目时：

- 列表字段取并集，保留历史观察。
- `evidence` 由最新一次观察覆盖。
- `observed_count` 加一，`first_seen` 和 `last_seen` 扩展区间，`sources` 取并集。
- `refs` 最多保留最近 10 条。

`confidence` 由出现次数和来源多样性推导，不接受人工指定：

- `high`：`observed_count` 不低于 3 且来源不少于 2 种。
- `medium`：`observed_count` 不低于 2，或来源不少于 2 种。
- `low`：其余情况。

同一条洞察被访谈说过、又被平台评论验证到，才会达到 `high`。

## 写回原则

洞察不自动写回。任何通道都先产出补丁，向用户展示将要新增和更新的条目，得到确认
后再执行 `insights-merge`。
