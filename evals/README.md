# Skill Evals

`<skill>/evals/evals.json` 记录每个 Skill 对模型的行为约束：一条用户输入，加一组
必须在会话中被满足的期望。这些约束只在提示词层面生效，`tests/` 里的单元测试覆盖
不到，改一句 SKILL.md 就可能悄悄失效。

`run_evals.py` 用真实 Agent 跑这些 case，再用一次裁判调用逐条判定。

## 运行

```bash
python3 evals/run_evals.py \
  --skill ugc-image-post \
  --agent-command 'codex exec --skip-git-repo-check {prompt}' \
  --max-cases 3
```

命令模板必须包含 `{prompt}`（内联提示词）或 `{prompt_file}`（提示词文件路径）。
用 `{prompt_file}` 可以避开 shell 引号问题。省略 `--judge-command` 时裁判复用同一个
命令。

`{work_dir}` 会展开成该 case 专属的空工作目录。把它接到 Agent 的工作目录参数上
（codex 是 `-C`），可以避免本仓库的 `AGENTS.md` 和 `CONTEXT.md` 混进上下文：

```bash
codex exec --skip-git-repo-check -C {work_dir} -s read-only --color never {prompt}
```

`--color never` 不是可选项——ANSI 转义码会污染交给裁判的会话记录。

## Fixtures

涉及本地素材的 case 必须自带素材，否则 Agent 只会回答"没找到文件"，判定没有意义。
在 case 上加 `fixtures` 字段，值是相对 `<skill>/evals/` 的目录：

```json
{
  "id": "route-decision-ready",
  "prompt": "工作目录里有对标图、对标文案和产品图，你看着办。",
  "fixtures": "assets/benchmark-and-product",
  "expected": ["..."]
}
```

runner 每次执行前会清空并重建工作目录，再把该目录下的文件铺进去。`prompt` 里要
明确说素材在工作目录，Agent 才会去找。

执行前先确认目标 Skill 已经安装到该 Agent 的运行时里——case 检验的是 Skill 被触发
后的行为，不是从零推理的结果。

常用参数：

| 参数 | 作用 |
| --- | --- |
| `--case <id>` | 只跑指定 case，可重复；id 不存在时立即报错，不会产生任何调用 |
| `--max-cases <n>` | 只跑前 n 条 |
| `--repeat <n>` | 每条 case 跑 n 次，按通过率汇总（见下） |
| `--dry-run` | 只写出提示词文件，不执行任何命令 |
| `--output-dir` | 默认写到 `.brand_ugc/evals/<skill>/<时间戳>/` |
| `--timeout` | 单次命令超时，默认 900 秒 |

先用 `--dry-run` 确认命令模板拼接正确，再跑真实调用。每个 case 都是一次完整的
Agent 会话加一次裁判调用，会产生真实费用。

## 为什么要 `--repeat`

Agent 会话是随机的。实测中同一条 case、同样的环境，相邻两次运行里 Agent 一次读了
Skill 说明书、一次完全没读，判定从 4/4 掉到 2/4——而两次之间什么都没改。

单轮的 pass/fail 因此读不出「改动是否有效」。用 `--repeat 3` 得到的是通过率：

```
✅ pass    3/3   规则写得够硬，稳定照做
🌀 flaky   1/3   有时照做有时不照做——通常是规则写得含糊
❌ fail    0/3   稳定不照做，真问题
```

`flaky` 比稳定失败更值得先修：稳定失败往往是期望写错了，而 flaky 说明 Skill 里
确实有一条规则模型看得见但不当回事。有 flaky 时退出码是 `1`。

## 输出

每个 case 一个目录，含 `agent.prompt.txt`、`transcript.txt`、`judge.prompt.txt`、
`judge.raw.txt`、`judgement.json`。根目录下是 `report.json` 和 `report.md`。

退出码：全部通过为 `0`，有 case 未通过或异常为 `1`，参数或配置错误为 `2`。

## 判定规则

裁判被要求只依据记录中实际出现的内容判断，找不到证据一律判 false。以下情况记为
`error` 而不是 `pass`，避免把失败读成成功：

- Agent 命令非零退出
- 裁判输出里找不到 JSON
- 裁判判定的条数与期望条数不一致

## 新增 case

在对应 `<skill>/evals/evals.json` 的 `evals` 数组里追加：

```json
{
  "id": "kebab-case-id",
  "prompt": "会诱导模型违反约束的用户输入",
  "expected": ["一条可以在会话记录里找到证据的具体行为"]
}
```

`prompt` 写成会诱导违约的说法（"不用问我"、"我要 12 张"、"跑到过为止"），断言才
有区分度。`expected` 每条都要能在记录里找到证据，不要写"输出质量好"这类无法判定的
描述。

`tests/test_skill_evals.py` 会校验文件结构、id 唯一，以及 `skill` 字段与 SKILL.md
frontmatter 的 `name` 一致。
