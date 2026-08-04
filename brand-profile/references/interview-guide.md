# 洞察访谈提纲

通过对话把运营脑子里的消费者认知转成 `insights.json`。产出是一份
`source` 为 `interview` 的补丁，按 `schemas/brand-insights-patch.schema.json`
组织，确认后由 `insights-merge` 写入。

## 访谈原则

- 一次只问一个问题，等回答后再问下一个。
- 优先问「你听到过什么」，而不是「你认为什么」。前者是信号，后者是假设。
- 对方给出抽象表述时追问一次具体场景或原话，追问一次没有结果就记录抽象版本，
  不要反复逼问。
- 不替对方补全。没问到的分区就不写进补丁。
- 一次访谈聚焦一到两个人群。人群太多会让每个都很浅。

## 分流：哪些不该进洞察

访谈中出现下面这类内容时，不要写进补丁：

- 可举证的产品事实（成分、容量、认证、检测数据、销量）走 `profile.json` 的
  `verified_claims`，需要 `evidence`。
- 品牌语气规范、禁用词、默认 CTA 和话题标签走 `profile.json` 的 `voice`、
  `compliance`、`defaults`。
- 竞品对比主张要有可举证的 `evidence` 才写入 `differentiation`；对方只是「感觉
  我们更好」时不记录。

## 问题分组

### 人群（`audience_insights`）

先确认这一轮聊哪个人群，用对方自己的说法命名，不要改写成营销标签。

- 痛点（`pain_points`）：这类人来找这个产品之前，最近一次让他们烦的具体情况是
  什么？发生在什么时候？
- 场景（`scenarios`）：他们通常在什么时间、什么状态下用这个产品？
- 顾虑（`objections`）：下单前最后一个犹豫是什么？退货和差评最常见的理由是
  什么？客服被问最多的问题是什么？
- 原话（`native_phrases`）：在客服记录、评论区或朋友口中，他们**原话**是怎么
  说的？

问原话时如果对方给的是书面语（例如「改善肌肤暗沉」），追问一次：客服记录里他们
实际打的字是什么。拿不到就不记 `native_phrases`。

### 内容方向（`content_pillars`）

- 有哪些话题是这个品牌可以反复讲、且每次都有新东西可说的？
- 每个方向能展开哪些具体角度（`angles`）？
- 这个方向主要讲给哪类人听（`audiences`）？

三到五个即可。超过五个通常说明方向拆得太细。

### 差异化（`differentiation`）

- 和哪个竞品或哪种品类通行做法比？（`vs`）
- 具体差在哪一点？（`point`）
- 凭什么这么说？（`evidence`，必填，没有就不记录）

### 表达库（`language_bank`）

- `voice_samples`：品牌已发布内容里，自己觉得写得最对味的句子。
- `hook_patterns`：过去用过且有效的开头句式，记原句，不要归纳成书面语。
- `title_formulas`：这些有效标题属于哪种公式，只填 `number`、`question`、
  `pain-point`、`result`、`urgency`、`authority`。问的是结构，不是句子；用户说不
  清就别硬套。
- `avoid_patterns`：明确不想出现的表达（区别于 `compliance` 的合规红线，这里是
  风格取向）。

## 产出补丁

只填问到的分区。`product_ids` 只在洞察确实只适用于某个产品时填写，品牌通用的
留空。

```json
{
  "brand_id": "<brand-id>",
  "source": "interview",
  "observed_at": "YYYY-MM-DD",
  "ref": {"note": "2026-08-03 运营访谈"},
  "audience_insights": [
    {
      "audience": "熬夜加班的25-30岁女性",
      "pain_points": ["第二天全脸暗沉，底妆卡粉"],
      "scenarios": ["加班到凌晨的卸妆后"],
      "objections": ["怕搓泥", "怕闷痘"],
      "native_phrases": ["急救", "回血", "第二天不垮脸"]
    }
  ]
}
```

## 收尾

先向用户展示补丁里将要新增和更新的条目，得到确认后再执行 `insights-merge`。

首次访谈得到的条目 `confidence` 是 `low`，这是预期结果：单一来源单次观察本来就
不该被当成高置信信息。后续被本地素材或平台回流重复验证到，置信度会自动上升。
