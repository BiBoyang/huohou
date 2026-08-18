# 火候（huohou）

个人的 AI agent skill 合集。火候：知道什么时候该等、什么时候该收、什么时候该关火——每个 skill 是一条练到成本能的工作纪律。遵循 `SKILL.md` + `references/` 的渐进加载结构。

## 安装

```bash
# 全部安装到共享目录（Claude Code / Codex / Kimi Code / Cursor 等自动可见）
npx skills add BiBoyang/huohou -g -y

# 更新
npx skills update -g -y
```

也可以手动把单个 skill 目录复制或软链到 `~/.claude/skills/` 或各 agent 的 skills 目录。

## 收录

工程线：`huohou-plan-first`（动手前）→ 写码（`huohou-recover-from-errors` 护航）→ `huohou-code-review`（写完）→ `huohou-wrap-up`（发布）；`huohou-collab-mode` 是大任务的可选增强模式。
内容线：`huohou-digest`（输入）→ `huohou-polish`（输出前）→ md2wechat（发布，不在本仓库）。

| Skill | 用途 | 触发 |
|---|---|---|
| `huohou-plan-first` | 动手前先出方案：根因分析/候选设计、取舍、验证方式，列出待拍板决策后停下等「开干」 | 修改代码 / 实现功能 / 修 bug / 重构前强制；只读 review、解释、调研不触发 |
| `huohou-recover-from-errors` | 报错防漂移：回锚点核对，修因不修表，三次不过即停 | 工具/命令反复报错时强制 |
| `huohou-code-review` | 通用评审流程与纪律（提炼自 deepseek-harness），含 Ousterhout Red Flags 清单 | review PR/diff、代码评审 |
| `huohou-wrap-up` | 开发收尾与发布链路：session 日志、README 同步、校验、commit、tag | `收尾` / `收尾并发布` |
| `huohou-collab-mode` | 协作模式入口：WORKFLOW.md 协议 + 拓扑并行调度 + 证据制验收 | `协作模式` / `退出协作模式` |
| `huohou-digest` | 研究消化：把书/源码/长文提炼成结构化学习笔记，含"知识还是习惯"的固化判断 | "帮我消化/学习/研究 X" |
| `huohou-polish` | 写作润色：按"事实>前提>逻辑>废话>代码>边界>术语>语气"优先级动刀，保原意和个人风格；附技术文章专项清单（12 问自检）和去 AI 味诊断规则（先治结构均匀化，再清词面） | "帮我润色/看看这段文字" |
| `huohou-swift-concurrency` | Swift 并发专家：数据竞争诊断、async/await 迁移、actor 隔离、Swift 6 迁移（收编自 [Swift Concurrency Course](https://www.swiftconcurrencycourse.com) 的 skill，已同步上游 v2.3.0，保留英文原文） | Swift 并发问题、Swift 6 迁移 |
| `huohou-rust-expert` | Rust 专家：借用检查器诊断（E0502/E0499 等）、生命周期、Send/Sync、错误处理、async/tokio、unsafe 审查；先理解"借用检查器在防什么"再给最小安全修复 | Rust 报错、并发、错误处理设计 |

## 规范

- 每个 skill 一件事，description 里穷举触发场景和关键词
- SKILL.md 只放快速路径，细节进 `references/`
- 每个 skill 写清"做完怎么验证"
- 新增 skill 时更新上表
