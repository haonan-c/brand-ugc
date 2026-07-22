# brand-ugc：品牌 UGC 生成

面向品牌生成 UGC 视频分镜与生产级提示词。本教程以 Windows 为主，也适用于
macOS 和 Linux。用户不需要配置模型，
只需要一个 EvoLink API Key、对标视频和产品图。

流程最终输出：

- 最终 12 宫格分镜图
- 可直接使用的 15 秒 Seedance 总提示词
- 12 条逐镜头运动指令
- 每一步结构化过程文件和 QA 报告

本流程不直接生成 MP4。用户把最终分镜图和提示词放到 Seedance 生成视频。

## 第一步：获取 EvoLink API Key

打开：

[EvoLink API Key 管理页](https://evolink.ai/dashboard/keys)

注意：

- 只需要一个 EvoLink API Key。
- 同一个 Key 用于视频/音频/图片理解、脚本、视觉 QA 和生图。
- 不要把 Key 发到聊天、飞书或截图中。
- Key 只保存在本地环境变量或 txt 文件。
- 原服务商的 Key 不能使用。

## 第二步：安装两个 Skill

下载并解压：

```text
brand-ugc.zip
```

把以下两个文件夹复制到 Codex Skills 目录：

```text
brand-ugc
imagegen-api
```

Windows 默认位置：

```text
C:\Users\<用户名>\.codex\skills\brand-ugc
C:\Users\<用户名>\.codex\skills\imagegen-api
```

macOS/Linux 默认位置：

```text
~/.codex/skills/brand-ugc
~/.codex/skills/imagegen-api
```

检查本机已有：

- Python 3.10 或更高版本
- FFmpeg
- FFprobe

本版本的十二宫格拼接直接使用 FFmpeg，不需要额外安装 Pillow。

## 第三步：保存 API Key

推荐设置环境变量：

```text
EVOLINK_API_KEY
```

也可以把 Key 写入：

```text
C:\Users\<用户名>\.codex\skills\imagegen-api\secrets\api_key.txt
```

macOS/Linux 对应：

```text
~/.codex/skills/imagegen-api/secrets/api_key.txt
```

为了兼容旧安装，程序仍会读取环境变量名 `IMAGEGEN_API_KEY`，但变量内容必须是
EvoLink Key。

不要在聊天里粘贴真实 Key。

## 第四步：重启 Codex

关闭并重新打开 Codex，让它识别新安装的 Skill。

## 第五步：准备素材

必须：

- 一个 15 秒左右的对标视频
- 一张产品图或产品多宫格图

可选：

- 人物参考图
- 文案 txt
- 产品名称、可验证卖点和限制

人物图未提供时，流程不会复制对标视频中的可识别真人；需要人物的镜头会使用
非真实虚构演员。

## 第六步：发给 Codex

上传素材后发送：

```text
请使用 brand-ugc 运行一个 15 秒品牌 UGC 视频案例。

我已上传：
1. 对标视频
2. 产品图
3. 人物图（如果有）
4. 文案（如果有）

产品名称：
这里填写产品名

产品备注：
- 只使用我提供的事实和产品图中直接可见的内容
- 缺少的信息标记“需要确认”
- 不要字幕、水印、平台 UI
- 有人物图时统一使用参考人物

请从视频解析开始完整执行，默认生成 2K 图片。
最后直接在聊天中输出最终十二宫格图和完整 Seedance 总提示词。
```

流程会依次显示：

1. `视频解析完成`
2. `12宫格参考图完成`
3. `新分镜脚本完成`
4. `12分镜提示词完成`
5. `第一步模板图完成`
6. `最终分镜图完成`
7. `视频提示词完成`

## 中断后继续

同名任务不会自动覆盖，以避免重复计费。如果运行中断，使用原命令并添加：

```text
--resume
```

程序会：

- 跳过已完成阶段
- 继续未完成阶段
- 已有 EvoLink 图片任务 ID 时只查询状态，不重复提交

如果素材发生变化，请换一个新的 `--run-name`，不要在旧任务上恢复。

## 输出位置

默认保存在：

```text
runs/brand-ugc/<任务名>/
```

重点文件：

```text
progress.json
进度.txt
stage_summary.json
qa/QA报告.json
outputs/12镜头解析.json
outputs/12镜头解析.md
collages/12宫格参考图.jpg
outputs/新产品-12分镜脚本.json
outputs/新产品-12分镜脚本.md
outputs/1-12分镜提示词.json
outputs/1-12分镜提示词.md
images/step1_template*/image-01.png
images/final_storyboard*/image-01.png
outputs/视频提示词1-12.json
outputs/视频提示词1-12.txt
```

JSON 是流程内部唯一数据源；Markdown 和 TXT 是给人阅读的展示版本。

## 常见问题

### 原视频会上传吗？

不会。程序在本地生成最高 720p 的无声分析代理和单声道音轨，只发送这两个派生
文件。原视频只用于本地抽取十二帧。

### 2K 失败会自动改成 1K 吗？

不会。默认 2K 失败时会明确停止。只有用户主动使用 `--resolution 1K` 才生成
1K，并显示质量警告。

### 图片 QA 失败怎么办？

每个图片阶段最多自动纠错生成一次，并再次 QA。第二次仍失败时停止，同时保留
失败图片和 QA 报告，不把不合格图片传给下游。

### 会生成几个候选图？

每个图片阶段只生成一张，不批量生成候选。单次运行最多使用配置中的 14 次模型
业务请求，达到上限会停止以避免继续计费。
