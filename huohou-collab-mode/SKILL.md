---
name: huohou-collab-mode
description: <MANDATORY>用户发送「协作模式」或明确表达进入时调用；发送「退出协作模式」时退出。</MANDATORY> 协作模式协议入口：固定"用户实现 + 助手规划/Review"的分工，详细协议读根目录 WORKFLOW.md。本 skill 是触发器和增强层，不重复协议本体。
---

# collab-mode（协作模式）

## 激活与退出

- 用户发送 `协作模式` / 明确表达进入 → **先读根目录 `WORKFLOW.md`**，按其中的角色分工、流程、模板执行
- 用户发送 `退出协作模式` → 退出协议，回到常规模式
- 协议本体（Task Brief、Plan Card、Review Card、DoD、记录文件规范）都在 WORKFLOW.md 里，以它为准；本 skill 只补充 WORKFLOW.md 没覆盖的执行增强

## 增强 1：多任务并行执行（当助手负责调度执行 agent 时）

WORKFLOW.md §4.5 定义了跨 agent 交接；调度多个执行任务时按拓扑分层跑，不要串行傻等也不要无脑全并行：

1. 把任务建成依赖图（每个任务声明它依赖哪些上游任务）
2. 按拓扑层级分批：**同层无依赖的任务并行派发，层与层之间串行**
3. 每个执行 agent 的提示词必须包含：任务文件绝对路径（`/.../<repo>/plans/TASK-<slug>.md`）、目标、涉及文件（同样用绝对路径）、验收标准、上游任务的产出
4. **所有路径一律用绝对路径**：提示词里不得只写项目相对路径（如 `plans/TASK-xxx.md`、`src/foo.ts`）。因为用户可能同时维护多个项目，只给相对路径无法定位到具体仓库；至少在首次提及时给出完整仓库根路径，后续同一 prompt 内可以配合相对路径说明，但仍必须保留可辨识的绝对锚点
5. 小任务（单文件 <30 行的改动）不派 agent，内联做掉，省编排开销
6. 执行 agent 命中 WORKFLOW.md 的硬停止条件时：收拢它的状态报告，升级给用户判断，不擅自重试

## 增强 2：证据制验收（Review Gate 前置）

提审前或 Review 时，逐项核对计划落地——**信证据不信记忆**：

1. 计划里说要创建/修改的文件：逐个打开验证内容符合计划
2. 计划里说要删的东西：确认真的删了
3. 计划里附了验证命令的：实际跑一遍，比对预期输出
4. 产出审计表：每个 step 标 `Done / Partial / Missing` + 证据
5. 发现缺口**只报告不擅修**——由用户决定补修还是调整计划（WORKFLOW.md 的分工：用户实现，助手规划和 Review）

## 增强 3：与单任务 skill 的衔接

- 协作模式内的**计划阶段**：复用 `huohou-plan-first` 的方案纪律（候选方案、取舍、验证方式），但产出形式按 WORKFLOW.md 的 Plan Card
- **Review Gate**：复用 `huohou-code-review` 的检查清单，结论只出 `Approved` / `Changes Requested`
- 协议外冲突时优先级：项目 AGENTS.md > 全局 AGENTS.md > WORKFLOW.md > 本 skill
