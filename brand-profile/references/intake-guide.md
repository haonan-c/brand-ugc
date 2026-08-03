# 本地素材提炼规则

从用户提供的本地文件中提炼洞察，产出 `source` 为 `local_asset` 的补丁。

## 适合的素材

- 客服问答记录、售后工单：`objections` 和 `native_phrases` 的最好来源。
- 已发布内容和评论导出：`native_phrases`、`hook_patterns`。
- 官网文案、产品详情页：`content_pillars`、`voice_samples`。
- 检测报告、认证文件：属于事实层，走 `profile.json` 的 `verified_claims`。
- 用户调研报告：`pain_points`、`scenarios`。

只读取用户明确提供的本地文件。不要顺着素材里的链接抓取站外内容。

## 提炼规则

- 逐个素材处理，每份素材单独产出一个补丁，`ref.note` 记录素材文件名。
- 只提炼素材中真实出现的表述，不做跨素材归纳，不补全缺失信息。
- 一份素材反复出现同一诉求时，记录一次即可；重复计数由 `insights-merge` 按合并
  次数计算，不要在补丁里堆同义条目。
- 官网文案是品牌自述，不是消费者语言。它可以进 `voice_samples` 和
  `content_pillars`，不能进 `native_phrases`。
- 客服记录里用户实际打的字才是 `native_phrases`，客服的回复话术不是。

## 分流

- 可举证的产品事实走 `profile.json` 的 `verified_claims`，需要 `evidence`。
- 素材里的竞品对比只有带得出证据时才写入 `differentiation`。
- 素材是官方合规文件时，禁用表述走 `profile.json` 的 `compliance`，不是
  `language_bank.avoid_patterns`。

## 脱敏

素材里常见的个人信息必须在提炼阶段丢弃，不进入补丁：

- 用户昵称、账号 ID、手机号、订单号、地址、邮箱。
- 客服工号和内部系统链接。
- 站外链接。

保留的是短语和归纳后的表述。原文含个人信息时改写成不含标识的版本，改写不下去就
不记录这一条。

## 收尾

向用户展示将要新增和更新的条目，确认后执行 `insights-merge`。素材提炼的条目
`confidence` 起点是 `low`，被访谈或平台回流交叉验证后自动上升。
