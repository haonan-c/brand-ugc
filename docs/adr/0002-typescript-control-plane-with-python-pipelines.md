# TypeScript 控制面保留现有 Python 流水线

运营工作台、API、任务编排和 Pi Agent 驱动使用 TypeScript 实现，现有 Python 图文与分镜流水线在第一版继续保留，由 TypeScript Worker 通过版本化 JSON 契约调用。现有流水线已经具备审批、预算、断点恢复和防重复提交能力，一次性重写风险高；只有在契约测试与双跑验证稳定后，才按流水线逐步迁移到 TypeScript。
