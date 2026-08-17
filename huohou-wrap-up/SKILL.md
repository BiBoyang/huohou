---
name: huohou-wrap-up
description: <MANDATORY>用户发送「收尾」「收尾并发布」，或要求提交/推送/发布/打 tag 时必须调用本 skill。</MANDATORY> 开发收尾与发布链路：更新 session 日志、按需同步 README、跑基础校验、一次性给出 commit message 草案与命令预览，用户回复 o 后提交推送；发布模式追加语义化版本升级、annotated tag 与推送。
---

# wrap-up（收尾）

当用户发送 `收尾`、`收尾并发布`，或明确要求"提交 / 推送 / 发布 / 打 tag"时触发。这是一个**合并执行的完整链路**，不要拆成多轮占位确认。

## 触发模式

| 口令 | 范围 |
|---|---|
| `收尾` | 更新 session 日志 → 同步 README → 基础校验 → 起草 commit message，等用户 `o` 后提交并推送 |
| `收尾并发布` | 在"收尾"基础上追加：语义化版本升级 → 同步版本文档 → 打 tag → 推送分支和 tag |

用户在此链路中单独回复 `o`：视为同意继续执行后续步骤，直到完成或出现真实阻断（报错/冲突/权限）。

## 收尾流程（按顺序执行）

### 1. 更新 session 日志

- 文件：`sessions/SESSION-YYYY-MM-DD.md`（项目根目录下，按当天日期）
- 不存在则按 `references/session-template.md` 的模板创建
- 记录：今天做了什么、关键决策、遗留问题
- 若项目没有 `sessions/` 目录的先例，先问用户是否要建立这个惯例

### 2. 同步 README（仅当有用户可见行为变化时）

- 判断标准：新增/删除/改变了命令、参数、配置项、用户可见输出
- 纯内部重构、bug 修复不改变行为 → 跳过此步

### 3. 基础校验

- 至少跑构建级检查：Rust 项目 `cargo check`，其他项目用对应的快速校验（`tsc --noEmit`、`go build ./...`、`swift build` 等）
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
- **敏感文件闸门**：commit 前检查 `git diff --staged --name-only`，命中 `.env`、`*.pem`、`*.key`、`id_rsa`、`node_modules/`、构建产物 → 立即停止并确认
- **范围闸门**：staged 文件包含本次任务范围外的改动 → 停止并确认
- **主分支闸门**：当前在 `main`/`master` 且用户未明确要求直推 → 停止并确认
- **推送**：首次推送用 `GIT_TERMINAL_PROMPT=0 git push` fail-fast；被 remote 拒绝（non-fast-forward）→ `git pull --rebase` → 解决冲突 → 再推
- **禁止**未经授权的 `push -f` / `--force-with-lease`、`reset --hard` 等破坏性操作

## 发布追加流程（`收尾并发布`）

1. **版本升级**：语义化最小升级（默认 patch，除非本次有明显的新功能/破坏性变化）；同步更新所有版本字段（`Cargo.toml` / `package.json` / 文档中的版本号）
2. **打 tag**：annotated tag，格式 `vX.Y.Z`：
   ```bash
   git tag -a vX.Y.Z -m "release: vX.Y.Z"
   ```
3. **推送**：分支和 tag 一起：`git push && git push origin vX.Y.Z`
4. tag 与推送 tag 属于本链路的高风险节点——已在第 4 步草案中列出并获得 `o` 即可，不要二次确认

## 红线

- 整条链路**只在首个高风险节点确认一次**（即第 4 步给出草案等 `o`），之后不再重复确认
- 未获明确要求，绝不执行破坏性操作
- 出现真实阻断（校验失败、推送冲突、权限问题）才停下报告；能自己解决的（如 rebase 冲突很小）先解决再继续
