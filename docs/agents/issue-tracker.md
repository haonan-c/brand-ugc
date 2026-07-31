# Issue tracker: GitHub

本仓库的开发规格和任务使用 GitHub Issues 管理。所有操作通过 `gh` CLI 完成，命令在
仓库目录内运行，由 Git remote 自动解析目标仓库。

## 常用操作

- 创建：`gh issue create --title "..." --body "..."`
- 阅读：`gh issue view <number> --comments`
- 列表：`gh issue list --state open --json number,title,body,labels,comments`
- 评论：`gh issue comment <number> --body "..."`
- 标签：`gh issue edit <number> --add-label "..."` 或 `--remove-label "..."`
- 关闭：`gh issue close <number> --comment "..."`

多行 issue body 使用 heredoc，避免转义和格式丢失。

## Pull requests 作为需求入口

**PRs as a request surface: no.**

外部 Pull Request 不进入需求 triage 队列。GitHub 的 Issue 和 Pull Request 共用编号；
遇到裸编号时先用 `gh pr view <number>` 判断，不存在时再使用
`gh issue view <number>`。

## Skill 约定

- “发布到 issue tracker”表示创建 GitHub Issue。
- “获取相关 ticket”表示执行 `gh issue view <number> --comments`。
- `/to-tickets` 生成的任务已经可执行，不再经过 `/triage`。

## 多任务、阻塞与 Wayfinder

- 一个规划地图使用带 `wayfinder:map` 标签的 GitHub Issue。
- 子任务优先使用 GitHub Sub-issues；不可用时，在地图正文使用任务列表，并在子任务顶部
  写入 `Part of #<map>`。
- 阻塞关系优先使用 GitHub 原生 issue dependencies；不可用时，在任务顶部写入
  `Blocked by: #<number>`。
- 只有全部 blocker 已关闭且任务未被认领时，任务才进入可执行队列。
- 认领任务使用 `gh issue edit <number> --add-assignee @me`。
- 完成任务后先评论实现结论，再关闭 Issue。
