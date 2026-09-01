---
name: huohou-wrap-up
description: <MANDATORY>用户发送「收尾」「收尾并发布」，或要求提交/推送/发布/打 tag 时必须调用本 skill。</MANDATORY> 触发口令：「提交」「推送」「收尾」「收尾并发布」，及"提交吧""push 一下""发个版""打个 tag"。提交/推送/收尾/发布四种模式边界分明：提交默认 commit+push（明说「只提交」除外），推送只 push；收尾更新 session 日志、按需同步 README、跑基础校验、给出 commit message 草案与命令预览等 o；发布模式追加语义化版本升级、annotated tag 与推送。不管：提交之前的代码改动与方案讨论——那是 plan-first 和 code-review 的地盘。
---

# wrap-up（收尾）

当用户发送 `收尾`、`收尾并发布`，或明确要求"提交 / 推送 / 发布 / 打 tag"时触发。按触发词进入对应链路；同一链路内合并执行，不拆成多轮占位确认。

## 触发模式

| 口令 | 范围 |
|---|---|
| `提交` / `commit` | **commit + push**（默认连带推送；用户明说"只提交 / 不推送"才止步于 commit） |
| `推送` / `push` | **只 push 当前已提交内容**，不新增 commit |
| `收尾` | 更新 session 日志 → 同步 README → 基础校验 → 起草 commit message，等用户 `o` 后提交；**是否 push 以用户口径为准**，未明说时在草案中明确写出 push 范围 |
| `收尾并发布` | 在"收尾"基础上追加：语义化版本升级 → 同步版本文档 → 打 tag → 推送分支和 tag |

四种模式边界清晰，不要把"提交"和"收尾并推送"混成一条链路。

`提交` 和 `推送` 是窄模式：只执行 Git 细则读取、仓库上下文核对、对应 Git 闸门和目标动作（提交 = commit + push，推送 = 仅 push）；不自动更新 session、同步 README 或新增版本变更，除非用户要求"收尾"。

确认语义：
- 用户直接说"提交吧 / commit"：视为**已授权 commit**，不再二次等 `o`；但仓库上下文核对、显式 add、staged 范围闸门、敏感文件闸门仍必须执行
- 任务链路中改动已展示并获确认（`o` / "执行吧" / "直接改"）后进入提交：**不再单独给 commit message 草案**，直接按已确认范围 commit + push；草案只在改动未经用户过目时给（如「收尾」模式）
- 用户说"收尾"：仍先给 commit message 草案和命令链路，等 `o`
- 发布链路只在草案处确认一次
- 用户在链路中单独回复 `o`：视为同意继续执行后续步骤，直到完成或出现真实阻断（报错/冲突/权限）

## 收尾流程（按顺序执行）

### 0. 读取仓库 Git 细则

进入提交/推送/发布前，先在目标仓库根目录读取 `GIT_WORKFLOW.md` 并遵循其中细则；文件缺失才按本 skill 的安全最小原则执行。

### 1. 更新 session 日志

- 文件：`sessions/SESSION-YYYY-MM-DD.md`（项目根目录下，按当天日期）
- 日期以本机 `date` 或用户提供的 current_date 为准；若已有最近 session 但日期不一致，**不要沿用旧文件**，说明差异后按当前日期创建
- 不存在则按 `references/session-template.md` 的模板创建
- 记录：今天做了什么、关键决策、遗留问题
- 若项目没有 `sessions/` 目录的先例，先问用户是否要建立这个惯例

### 2. 同步 README（仅当有用户可见行为变化时）

- 判断标准：新增/删除/改变了命令、参数、配置项、用户可见输出
- 纯内部重构、bug 修复不改变行为 → 跳过此步

### 3. 基础校验

- 至少跑构建级检查：Rust 项目 `cargo check`，其他项目用对应的快速校验（`tsc --noEmit`、`go build ./...`、`swift build` 等）
- **文档/skill-only 仓库**（没有构建入口）：不要硬跑 cargo/npm/swift，改做结构检查——`git diff` 核对改动、必要文件存在性、frontmatter/manifest 字段完整性，并在草案中说明无可运行构建
- 项目有测试且改动涉及逻辑 → 追加跑测试
- 校验不过 → 停下修复，不要带病提交

### 4. 一次性给出草案

不要分多轮问。一次性输出：
- **commit message 草案**（遵循仓库已有规范：有 commitlint/semantic-release 就遵守；否则一个逻辑改动一个 commit）
- **完整命令链路预览**
- 发布模式下附 **release note 草稿** 和新版本号（语义化最小升级，默认 patch）

然后等用户 `o` 继续。

## 提交与推送纪律（硬规则）

提交前必须核对仓库上下文：
```bash
pwd && git rev-parse --show-toplevel && git remote -v
```

- **显式 add**：`git add <file1> <file2> ...`，禁止 `git add .` / `git add -A`（用户明确要求除外）
- **敏感文件闸门**：commit 前做两层检查——
  1. 文件名：`git diff --staged --name-only` 命中 `.env`、`*.pem`、`*.key`、`id_rsa`、`node_modules/`、构建产物 → 立即停止并确认
  2. 内容：扫 staged diff 中的高风险字样（`api key`、`token`、`private key`、`password`、`secret` 等）和长随机凭据 → 命中立即停止并确认；若命中发生在文档/测试示例中，先判定是否为真实凭据，确认是假阳性后可继续，并在最终说明中提到已检查
- **范围闸门**：staged 文件包含本次任务范围外的改动 → 停止并确认
- **主分支闸门**：当前在 `main`/`master` 且用户未明确要求直推 → 停止并确认
- **推送**：首次推送用 `GIT_TERMINAL_PROMPT=0 git push` fail-fast
- **push 被拒绝（non-fast-forward）**：停止自动推送，先做只读排查——
  ```bash
  git status && git fetch && git log --left-right HEAD...@{u}
  ```
  不要自动 `git pull --rebase`。只有工作树干净、分叉原因明确、且用户确认后才 rebase；绝不自动解决冲突再推
- **禁止**未经授权的 `push -f` / `--force-with-lease`、`reset --hard` 等破坏性操作

## 发布追加流程（`收尾并发布`）

1. **版本升级**：语义化最小升级（默认 patch，除非本次有明显的新功能/破坏性变化）；升级前先读取当前版本字段；同步更新所有版本字段（`Cargo.toml` / `package.json` / 文档中的版本号）
2. **打 tag**：annotated tag，格式 `vX.Y.Z`。打之前先查现有 tag，确认新 tag 不存在：
   ```bash
   git tag -l 'v*' && git ls-remote --tags origin
   ```
   确认无冲突后：
   ```bash
   git tag -a vX.Y.Z -m "release: vX.Y.Z"
   ```
3. **推送**：分支和 tag 一起：`git push && git push origin vX.Y.Z`
4. tag 与推送 tag 属于本链路的高风险节点——已在第 4 步草案中列出并获得 `o` 即可，不要二次确认

## 红线

- 整条链路**只在首个高风险节点确认一次**（收尾/发布模式即第 4 步给出草案等 `o`；用户直接说"提交"时已授权 commit），之后不再重复确认
- 未获明确要求，绝不执行破坏性操作
- 出现真实阻断（校验失败、push 被拒绝、权限问题）才停下报告；push 被拒绝一律先只读排查再听用户指示，不要自动 rebase / 解冲突
