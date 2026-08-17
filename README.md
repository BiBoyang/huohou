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

工程线：`plan-first`（动手前）→ 写码（`recover-from-errors` 护航）→ `code-review`（写完）→ `wrap-up`（发布）；`collab-mode` 是大任务的可选增强模式。
内容线：`digest`（输入）→ `polish`（输出前）→ md2wechat（发布，不在本仓库）。

| Skill | 用途 | 触发 |
|---|---|---|
| `plan-first` | 动手前先出方案：根因分析/候选设计、取舍、验证方式，列出待拍板决策后停下等「开干」 | 处理 issue、新功能、重构前强制 |
| `recover-from-errors` | 报错防漂移：回锚点核对，修因不修表，三次不过即停 | 工具/命令反复报错时强制 |
| `code-review` | 通用评审流程与纪律（提炼自 deepseek-harness），含 Ousterhout Red Flags 清单 | review PR/diff、代码评审 |
| `wrap-up` | 开发收尾与发布链路：session 日志、README 同步、校验、commit、tag | `收尾` / `收尾并发布` |
| `collab-mode` | 协作模式入口：WORKFLOW.md 协议 + 拓扑并行调度 + 证据制验收 | `协作模式` / `退出协作模式` |
| `digest` | 研究消化：把书/源码/长文提炼成结构化学习笔记，含"知识还是习惯"的固化判断 | "帮我消化/学习/研究 X" |
| `polish` | 写作润色：去翻译腔和 AI 八股、砍废话，保原意和个人风格 | "帮我润色/看看这段文字" |

## 规范

- 每个 skill 一件事，description 里穷举触发场景和关键词
- SKILL.md 只放快速路径，细节进 `references/`
- 每个 skill 写清"做完怎么验证"
- 新增 skill 时更新上表
