# 小红书选题雷达

`xhs-topic-radar` 是 brand-ugc 的选题研究入口。它把真实搜索联想、笔记和评论整理为本地证据包，再由 Agent 生成并校验十张可直接进入创作的策略卡。

## 安装与要求

```bash
npx -y skills@latest add haonan-c/brand-ugc \
  --skill ask-brand xhs-topic-radar ugc-image-post ugc-storyboard brand-profile image-generator \
  --agent codex --global --yes
```

要求 Node.js `>=22.5.0`。TikHub 请求使用用户自己的 Key。推荐先运行初始化：

```bash
python3 ~/.agents/skills/setup-brand-ugc/scripts/setup_check.py init \
  --project-root "$PWD"
```

然后在可信编辑器中填写项目 `.brand_ugc/credentials.json` 的 `tikhubApiKey`。以后该项目会自动读取，不需要重复设置环境变量。也可运行隐藏输入命令更新同一文件：

```bash
node ~/.agents/skills/xhs-topic-radar/scripts/topic_radar.mjs key set \
  --workspace "$PWD"
```

环境变量 `TIKHUB_API_KEY` 仍可临时覆盖项目配置。切勿把 Key 放进聊天、日志或命令参数。

## 标准运行

以下命令中的工作目录是品牌项目目录；雷达数据自动写入其 `.brand_ugc/topic-radar/`。

### 1. 配置行业与周期

```bash
node ~/.agents/skills/xhs-topic-radar/scripts/topic_radar.mjs setup \
  --workspace "$PWD" --industry "软件著作权代理服务" --lookback-days 7
```

软著行业默认配额为大学生 4、高新技术企业 3、杭州 E 类人才 3。其他行业默认生成十个通用人群选题。

### 2. 预览真实需求词

```bash
node ~/.agents/skills/xhs-topic-radar/scripts/topic_radar.mjs preview \
  --workspace "$PWD"
```

这一步通常只产生 3 次付费搜索联想请求。返回值包含原样 seed/terms、已用费用、剩余请求和预计费用、计划文件路径。此后必须停止，等待用户明确确认。

### 3. 确认后采集

```bash
node ~/.agents/skills/xhs-topic-radar/scripts/topic_radar.mjs collect \
  --workspace "$PWD" --plan "/absolute/data/plans/<plan-id>.json" --approve
```

CLI 会验证计划日期和配置签名，并保留以下保护：

- 官方价格接口预检；
- 余额/赠送额度预检；
- 最多 27 次 TikHub 业务请求；
- 预计费用硬上限 US$0.30；
- 请求节流、错误脱敏和并发运行锁；
- 原始响应、SQLite 历史、评论问题和证据包本地保存。

未传 `--approve` 时，命令在读取计划和发起采集请求前失败。

### 4. 生成并校验策略卡

Agent 完整读取 `data/pending/<run-id>.json`，按 `schemas/topic-candidates.schema.json` 生成 JSON 数组，然后执行：

```bash
node ~/.agents/skills/xhs-topic-radar/scripts/topic_radar.mjs finalize \
  --workspace "$PWD" --run-id "<run-id>" \
  --topics-file "/absolute/<run-id>-topics.json"
```

最终化会机械校验：数量与受众配额、必填策略字段、原样证据 URL、对应受众的需求词、六维加权分数、优先级、近期标题重复和风险表述。通过后写入：

```text
.brand_ugc/topic-radar/reports/YYYY-MM-DD.md
.brand_ugc/topic-radar/reports/YYYY-MM-DD.json
.brand_ugc/topic-radar/reports/latest.md
```

## 状态、报告与刷新

```bash
node ~/.agents/skills/xhs-topic-radar/scripts/topic_radar.mjs status --workspace "$PWD"
node ~/.agents/skills/xhs-topic-radar/scripts/topic_radar.mjs report --workspace "$PWD"
node ~/.agents/skills/xhs-topic-radar/scripts/topic_radar.mjs config --workspace "$PWD"
```

同一天、相同配置默认复用已有报告。只有用户明确要求付费刷新时，才在 `preview` 加 `--force`。

## 证据边界

- 搜索联想词是需求语言信号，不是精确搜索量。
- 单次搜索快照不能证明全平台趋势、算法偏好或必然爆款。
- 小红书笔记与评论不是事实、法律或政策权威。
- 价格、时效、资格、效果、政策与合规结论必须核验当前官方或权威来源，并禁止结果承诺。
- 选题完成后，应由用户选择一张策略卡，再启动独立的图文或视频生产任务。
