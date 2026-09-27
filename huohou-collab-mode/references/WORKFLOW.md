# Workflow Protocol（canonical 浓缩版）

> 本文件是协作模式协议的 canonical 副本，随 huohou 仓库版本化。
> 各项目根目录的 `WORKFLOW.md` 可与本文一致或按项目裁剪；冲突时优先级见 §8。

## 0. 激活

- 默认不自动启用。仅当用户发送 `协作模式`（或明确表达进入）时启用；`退出协作模式` 后回到常规模式。

## 1. 角色

- **Owner**（用户）：确认目标与边界；派发前审阅 Plan Card 与 PROMPT 文件（确认闸门，未确认不派发）；派发并收集上报，组装 Review Package；Review 通过后人工终审，手动 commit/push。
- **Planner**（助手）：建上下文、拆任务、落 TASK / PROMPT 文件、为每 step 定义 DoD、维护过程记录、执行结构化 Review。
- **Executor**（独立会话的执行 agent）：按 PROMPT 文件编码，不越出文件范围；完成一个 step 即上报，不跨步混改；命中硬停止即停并上报，不硬试、不回滚。

## 2. 流程

1. **需求**：Owner 给目标/范围/约束 → Planner 复述目标 + Out of Scope。
2. **计划**：Planner 出 Plan Card（现状、拆解、每步 DoD、验证命令），落 `plans/TASK-<slug>.md`（任务契约，长期保留）和 `prompts/TASK-<slug>.prompt.md`（初始 `status: pending`，即"已生成、待 Owner 确认"）。Planner 在会话里展示要点，**Owner 确认后才允许派发，未确认的文件不得派发**——文件化是交接载体，不是绕过 Owner 的自动化。
3. **实现**：Owner 派发（话术只需"读取 <PROMPT 文件绝对路径> 干活"），状态头改 `dispatched`；结束后改 `done` / `failed`，PROMPT 文件保留不删。
4. **Review Gate**：Owner 组装 Review Package 提审；Planner 按 Blocker/Major/Minor 出 findings；结论仅 `Approved` / `Changes Requested`。
5. **提交**：`Approved` 后 Owner 人工终审并手动 commit/push。

## 3. 跨 Agent 交接（文件化提示词模型）

- 交接只通过文件：TASK 是长期契约，PROMPT 是派发指令，两者分离。
- **Executor 默认是独立会话，由 Owner 手动派发；Planner 不得用 Agent/AgentSwarm 自行委派编码**（确认闸门在 Owner 手上）。唯一例外：Owner 当轮明确授权"你来调度"。只读调查类 subagent（explore/plan，不写文件）不受此限。
- PROMPT 文件自包含：Executor 只读它（及引用的 TASK 文件）即可开工。必备内容：状态头（task/status/from/to/created）、目标+成功标准、涉及文件、DoD、上游产出、硬停止条件与上报格式（内联全文）。
- 所有路径一律绝对路径，保留可辨识的绝对锚点。
- 任务粒度以"一次会话内可完成并验证"为上限。
- **硬停止条件**（命中任一即停并上报，不硬试、不回滚）：
  1. 同一处修改尝试超过 3 次仍未通过；
  2. 需要改动任务清单之外的文件；
  3. 测试/构建失败原因超出任务描述范围；
  4. 认为验收标准或任务范围本身有误、互斥或已过时。
- **只读约束**：TASK 文件与 PROMPT 文件整体（含状态头）对 Executor 只读，状态头由 Owner 维护；异议走硬停止 4 上报，不得修改。
- **过程记录**：Executor 每完成一个 step 或命中硬停止时，向 `prompts/TASK-<slug>.status.md` 追加一行（只追加不改已有行）：`时间 | step | done/blocked | 证据（命令+结果/文件路径） | 下一步`。status 文件为协议约定写入，不计入任务清单外改动。中断续跑先读 status 再读代码。上报必须附 status 文件路径，未写过程记录视为未完成。
- 提审前置：先过基础校验（测试/构建/lint），结果附 Review Package；未附可退回。
- 卡点升级（测试不过、改动滚大、同文件反复改）由 Owner 判断。

## 4. Definition of Done（默认）

每 step 至少：功能满足目标且边界有处理；范围清晰无无关修改；测试新增/更新且通过；基础校验通过；无回归/性能/兼容风险；文档同步；验证可复现（命令+结果）。

## 5. 模板

### Task Brief（Owner → Planner）
任务名 / 目标 / In Scope / Out of Scope / 约束 / 备注。

### Plan Card（Planner → Owner）
目标复述 / Out of Scope / Step 列表 / 每步 DoD / 风险与回滚点 / 建议先做的 step。

### Review Package（Owner → Planner）
Step 编号 / 改动文件列表 / 关键 diff 摘要 / 自测命令与结果 / status 文件路径（必填；未写过程记录即视为未完成，直接退回）/ 用户验收清单（每条含前置条件、说人话的操作步骤、通过标准、回传证据；无人工项写"无"）/ 已知风险。

### Review Card（Planner → Owner）
结论（Approved / Changes Requested）/ Findings（[Severity] 文件:行号 - 问题 - 影响 - 建议）/ 测试意见 / 残余风险 / 变更摘要。

### PROMPT 文件（Planner 产出，Owner 派发）

```markdown
---
task: /绝对路径/<repo>/plans/TASK-<slug>.md
status: pending
from: Planner
to: Executor
created: YYYY-MM-DD
---

# 任务：<任务名>

## 目标
<一句话目标 + 成功标准>

## 涉及文件（绝对路径）
- /绝对路径/<repo>/<file>

## 验收标准（DoD）
1. ...

## 上游任务产出
<无 / 说明>

## 硬停止条件（命中任一即停并上报，不硬试、不回滚）
1. 同一处修改尝试超过 3 次仍未通过；
2. 需要改动上述清单之外的文件；
3. 测试/构建失败原因超出本任务描述范围；
4. 认为验收标准或任务范围本身有误、互斥或已过时。

## 只读约束
TASK 文件与本文件整体（含 front matter 状态头）对你只读；状态头由 Owner 维护。
对验收标准有异议时，命中硬停止条件 4，停下上报，不得修改。

## 过程记录
- 每完成一个 step、或命中硬停止条件时，向 `/绝对路径/<repo>/prompts/TASK-<slug>.status.md` 追加一行：
  `YYYY-MM-DD HH:mm | step N | done/blocked | 证据（命令+结果 / 文件路径） | 下一步`
- 只追加，不修改已有行。中断续跑时，先读该 status 文件再继续干活。
- status 文件为协议约定写入，不计入「涉及文件」清单之外的改动。

## 上报格式
停止或完成时输出：当前状态（done / stopped）、已改动文件列表、
关键 diff 摘要、自测命令与结果、已知风险 / 卡点描述，
并附 status 文件绝对路径（未写过程记录视为未完成）。
```

## 6. 范围与变更纪律

- 默认一次只推进一个 step；多任务并行按 collab-mode skill 增强 1 的拓扑分层。
- 任务单之外的改动，需经 Owner 同意，并在提审时主动说明原因。
- 发现需求漂移先更新计划再开发；重大设计变更先过"计划更新 + 风险确认"。

## 7. 记录文件

- `sessions/SESSION-YYYY-MM-DD.md`：当日进展、结论、待办。
- `plans/TASK-<slug>.md`：任务契约，长期保留。
- `prompts/TASK-<slug>.prompt.md`：派发指令，状态头标记生命周期（pending/dispatched/done/failed），保留不删。
- `prompts/TASK-<slug>.status.md`：Executor 过程日志（append-only），中断恢复锚点，随 PROMPT 保留复盘。
- `reviews/REVIEW-<task>-<date>.md`：review findings 与结论。

## 8. 优先级

项目 `AGENTS.md` > 全局 `AGENTS.md` > 项目 `WORKFLOW.md` > 本文件；用户当轮明确指令优先于默认协议。
