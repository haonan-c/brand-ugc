# EvoLink 图片 API 合同

## 创建任务

```text
POST https://api.evolink.ai/v1/images/generations
Authorization: Bearer <EVOLINK_API_KEY>
Content-Type: application/json
```

```json
{
  "model": "gemini-3-pro-image-preview",
  "prompt": "生成一张写实产品图",
  "size": "9:16",
  "quality": "2K",
  "image_urls": ["https://files.evolink.ai/..."]
}
```

- `prompt`：最多 2000 tokens。
- `size`：比例字符串。
- `quality`：本 Skill 只允许 `1K` 或 `2K`。
- `image_urls`：本地图片先通过 EvoLink 文件服务上传。

创建成功后保存返回的 `id`，不要重复提交。

## 查询任务

```text
GET https://api.evolink.ai/v1/tasks/{task_id}
```

轮询 `pending`、`processing`、`completed`、`failed`。完成后立即下载
`results[0]`；远程结果链接只短期有效，不写入持久化日志。

## 文件上传

```text
POST https://files-api.evolink.ai/api/v1/files/upload/base64
```

请求使用 `base64_data` 和可选 `file_name`。上传响应中的临时 `file_url`
只在内存中传给生图请求，不写入日志或任务状态。
