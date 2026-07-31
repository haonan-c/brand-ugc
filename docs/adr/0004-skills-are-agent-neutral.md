# Skills 仓库对三个 agent 保持中立，专属治理只发生在运营工作台层

brand-ugc 仓库交付的核心资产是 `SKILL.md`/scripts 本身，对 Pi Agent、Codex、Claude Code 三个 agent 保持行为和结构中立，不做任何绑定某一个 agent 的专属集成；各 agent 的纯展示层元数据（如 `agents/openai.yaml`）是可接受的例外，不影响这条原则。Pi 专属的审批与工具收窄 Extension（`docs/pi-agent-driver-evaluation.md` 阶段二）属于运营工作台产品自身的治理层，只约束运营工作台如何使用 Pi，不代表 Skills 仓库本身偏向 Pi，也不代表 Codex/Claude Code 是二等公民。
