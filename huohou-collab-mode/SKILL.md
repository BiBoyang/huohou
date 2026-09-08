---
name: huohou-collab-mode
description: <MANDATORY>用户发送「协作模式」或明确表达进入时调用；发送「退出协作模式」时退出。</MANDATORY> 协作模式协议入口：固定"Owner（操作人）派发验收 + Planner（助手）规划/Review + Executor（执行 agent）编码"的三角色分工，详细协议读根目录 WORKFLOW.md。本 skill 是触发器和增强层，不重复协议本体。不管：单任务的方案评审——直接用 huohou-plan-first，不必进协作模式。
---

# collab-mode（协作模式）

## 激活与退出

- 用户发送 `协作模式` / 明确表达进入 → **先读根目录 `WORKFLOW.md`**，按其中的角色分工（Owner / Planner / Executor）、流程、模板执行
- 用户发送 `退出协作模式` → 退出协议，回到常规模式
- 协议本体（Task Brief、Plan Card、Review Card、PROMPT 文件模板、DoD、记录文件规范）都在 WORKFLOW.md 里，以它为准；本 skill 只补充 WORKFLOW.md 没覆盖的执行增强

## 增强 1：多任务并行执行（拓扑分层 + Owner 派发）

WORKFLOW.md §4.5 定义了文件化交接和派发通道；多任务并行时按拓扑分层组织，不要串行傻等也不要无脑全并行：

1. 把任务建成依赖图（每个任务声明它依赖哪些上游任务）
2. 按拓扑层级分批：**同层无依赖的任务进同一批，层与层之间串行**
3. Planner 的产出是**派发批次清单**：每批列出可并行的 PROMPT 文件绝对路径 + 一句话任务描述，Owner 复核后自行开新会话/进程派发——Planner 不擅自用 Agent/AgentSwarm 派 coder 干活
4. 每个任务的执行提示词必须落成 `prompts/TASK-<slug>.prompt.md`（模板见 WORKFLOW.md §6.3），派发现场不临时组装提示词——Owner 在会话里确认 Plan Card 后，直接拿文件喂给 Executor，派发话术只需"读取 <PROMPT 文件绝对路径> 干活"
5. **所有路径一律用绝对路径**：提示词里不得只写项目相对路径（如 `plans/TASK-xxx.md`、`src/foo.ts`）。因为 Owner 可能同时维护多个项目，只给相对路径无法定位到具体仓库；至少在首次提及时给出完整仓库根路径，后续同一文件内可以配合相对路径说明，但仍必须保留可辨识的绝对锚点
6. 小任务（单文件 <30 行的改动）不派 Executor，内联做掉，省编排开销
7. 例外——Owner 当轮明确授权"你来调度"时，Planner 可用 Agent/AgentSwarm 代调度 coder subagent：同批并行派发；Executor 命中 WORKFLOW.md 硬停止条件时，收拢状态报告升级给 Owner 判断，不擅自重试

## 增强 2：证据制验收（Review Gate 前置）

提审前或 Review 时，逐项核对计划落地——**信证据不信记忆**：

1. 计划里说要创建/修改的文件：逐个打开验证内容符合计划
2. 计划里说要删的东西：确认真的删了
3. 计划里附了验证命令的：实际跑一遍，比对预期输出
4. 产出审计表：每个 step 标 `Done / Partial / Missing` + 证据
5. 发现缺口**只报告不擅修**——由 Owner 决定补修还是调整计划（WORKFLOW.md 的分工：Executor 编码，Planner 规划和 Review）

## 增强 3：与单任务 skill 的衔接

- 协作模式内的**计划阶段**：复用 `huohou-plan-first` 的方案纪律（候选方案、取舍、验证方式），但产出形式按 WORKFLOW.md 的 Plan Card + TASK 文件 + PROMPT 文件。plan-first 本体不改——单会话任务不落提示词文件，避免纯开销
- **Review Gate**：复用 `huohou-code-review` 的检查清单，结论只出 `Approved` / `Changes Requested`
- 协议外冲突时优先级：项目 AGENTS.md > 全局 AGENTS.md > WORKFLOW.md > 本 skill
