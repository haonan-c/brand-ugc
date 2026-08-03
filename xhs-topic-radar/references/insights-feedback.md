# 洞察回流规则

把一次选题雷达采到的消费者语言沉淀到品牌上下文，让后续图文和视频有据可依。产出
是一份 `source` 为 `platform_radar` 的补丁，按 `brand-profile` 的
`schemas/brand-insights-patch.schema.json` 组织，由用户确认后交给
`brand-profile` 的 `insights-merge` 写入。

回流是报告完成之后的可选收尾动作，不是 `finalize` 的一部分。`finalize` 是校验
器，不产生副作用。

## 前提

- 用户已经有品牌档案，且明确了这次回流到哪个 `brand_id`。
- 用户明确同意沉淀。没有品牌档案时不要为了回流去创建一个。
- 雷达跑的是行业词，未必都与该品牌相关。只回流与品牌人群和品类真正相关的条目，
  其余丢弃。

## 两个来源

### 证据包评论（`evidence[].commentQuestions`）

真实消费者原话，是这次回流最有价值的部分。

| 评论内容 | 目标字段 |
| --- | --- |
| 描述使用中遇到的具体麻烦 | `pain_points` |
| 描述什么时候、什么状态下用 | `scenarios` |
| 购买前的犹豫、担心的副作用或后果 | `objections` |
| 反复出现的口头表达 | `native_phrases` |

排除下列评论，它们没有信息量：

- 纯交易意图：求链接、多少钱、哪里买、蹲一个。
- 纯情绪和表情：好看、姐妹冲、emoji。
- 与品类无关的闲聊和引流。

### 策略卡（`finalize` 后的选题）

| 策略卡字段 | 目标字段 |
| --- | --- |
| `demandKeywords` | `native_phrases` |
| `hook`、`titlePattern`、`titleAlternatives` | `language_bank.hook_patterns` |
| `userQuestion` | `pain_points` 或 `objections` |
| `contentGap`、`angle`、`targetScenario` | `content_pillars` |
| `doNotSay` | `language_bank.avoid_patterns` |

`demandKeywords` 来自真实搜索联想，是质量最高的消费者语言，优先回流。

## 硬约束

- **不写 `differentiation`。** 平台回流的是品类需求，不是对本品牌的评价，不能
  用来生成差异化主张。`insights-merge` 会直接拒绝。
- **不写事实层。** 评论里的功效、成分、价格、销量说法都是社交内容，不是事实，
  不能进 `profile.json` 的 `verified_claims`。
- **不整条保存评论原文。** 只提炼归纳后的表述和短语级原话。
- **不保存作者标识。** 昵称、用户 ID、主页链接、联系方式一律丢弃。
- `ref` 只填 `run_id` 和 `note_urls`，用于日后追溯证据来源。

## 人群归属

补丁里的 `audience` 用品牌已有的人群命名。这次雷达的 `audienceLabels` 是行业配额
标签，不是品牌人群，不要直接拿来当 `audience`。无法对应到已有人群时，先问用户这
批评论属于哪个人群，问不清就不回流这部分。

`product_ids` 通常留空：品类评论反映的是品牌级需求，不是某个具体产品的。

## 补丁示例

```json
{
  "brand_id": "<brand-id>",
  "source": "platform_radar",
  "observed_at": "YYYY-MM-DD",
  "ref": {
    "run_id": "<run-id>",
    "note_urls": ["https://www.xiaohongshu.com/explore/..."]
  },
  "audience_insights": [
    {
      "audience": "熬夜加班的25-30岁女性",
      "pain_points": ["第二天全脸暗沉，底妆卡粉"],
      "objections": ["怕搓泥"],
      "native_phrases": ["急救", "回血"]
    }
  ],
  "language_bank": {"hook_patterns": ["第二天不垮脸"]}
}
```

## 收尾

先向用户展示将要新增的条目和将要被再次验证的已有条目，确认后执行：

```bash
python3 <brand-profile>/scripts/manage_profile.py insights-merge \
  --brand-id "<brand-id>" \
  --patch-file "/absolute/path/to/insights-patch.json" \
  --output-root "<brand-workspace>/.brand_ugc"
```

同一条洞察被访谈说过、又被平台评论验证到，`confidence` 才会升到 `high`。所以重复
回流是预期行为，不是重复劳动。

## 不做反向注入

已积累的品牌洞察不参与选题生成。用它过滤或排序已经生成的选题可以，用它决定去生成
什么选题不行——那样雷达只会不断产出品牌已经知道的东西，失去发现新需求的能力。
