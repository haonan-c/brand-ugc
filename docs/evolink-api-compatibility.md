# EvoLink API 迁移说明

核查与实现日期：2026-07-21

## 当前状态

本发布包已完成 EvoLink 切换，不再调用旧的自定义网关。

| 能力 | EvoLink 实现 |
| --- | --- |
| 视频、音频、图片和文本理解 | Gemini Native `gemini-3.1-pro-preview` |
| 结构化输出 | `generationConfig.responseMimeType` + `responseJsonSchema` |
| 图片生成/编辑 | `gemini-3-pro-image-preview` |
| 本地图片上传 | EvoLink Base64 文件上传 |
| 图片任务 | 创建异步任务，持久化 ID，轮询并立即下载 |
| 余额预检 | `GET /v1/credits` |

## 固定接口

多模态分析：

```text
POST https://direct.evolink.ai/v1beta/models/gemini-3.1-pro-preview:generateContent
```

图片生成：

```text
POST https://api.evolink.ai/v1/images/generations
GET  https://api.evolink.ai/v1/tasks/{task_id}
```

图片上传：

```text
POST https://files-api.evolink.ai/api/v1/files/upload/base64
```

余额：

```text
GET https://api.evolink.ai/v1/credits
```

所有接口使用：

```text
Authorization: Bearer <EVOLINK_API_KEY>
```

官方资料：

- [Gemini 3.1 Pro Native API](https://docs.evolink.ai/en/api-manual/language-series/gemini-3.1-pro/native-api/native-api-reference)
- [Nano Banana Pro 图片生成](https://docs.evolink.ai/en/api-manual/image-series/nanobanana/nanobanana-pro-image-generate)
- [异步任务查询](https://docs.evolink.ai/en/api-manual/task-management/get-task-detail)
- [Base64 文件上传](https://docs.evolink.ai/en/api-manual/file-series/upload-base64)
- [余额查询](https://docs.evolink.ai/en/api-manual/account-management/get-credits)

## 隐私实现

- 原视频不进入远程请求。
- 本地 FFmpeg 生成最高 720p 无声代理和 16kHz 单声道音轨。
- 分析请求只发送代理和音轨。
- 原片只用于本地十二帧抽取。
- 产品图、人物图和生成图只在所需阶段发送。
- Base64、Authorization、上传凭据和临时 URL 不写入日志。

## 凭据兼容

读取顺序：

1. `EVOLINK_API_KEY`
2. 兼容环境变量名 `IMAGEGEN_API_KEY`
3. `image-generator/secrets/api_key.txt`

第二项只是变量名兼容，值仍必须是 EvoLink 密钥。EvoLink 返回 401 时，程序会
明确提示旧服务密钥不受支持。

## 生图参数

- 模型固定为 `gemini-3-pro-image-preview`。
- 默认 `quality=2K`。
- 允许用户显式选择 `1K`。
- 不允许默认 4K，也不允许 2K 失败后静默降级。
- `prompt` 按官方 2000-token 限制保守裁剪。
- 每阶段只生成一张；视觉 QA 失败最多纠错生成一次。

## 恢复与计费保护

- 同名运行默认拒绝覆盖。
- `--resume` 只继续未完成阶段。
- 图片任务 ID 在提交成功后立即写入本地状态。
- 已有任务 ID 时只轮询，不重新上传或创建任务。
- 单次运行最多 14 次模型业务请求；余额查询、文件上传和任务轮询不计入该预算。
