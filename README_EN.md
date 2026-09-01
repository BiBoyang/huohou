# huohou (火候)

[中文](README.md) | **English**

A personal collection of AI agent skills. *Huohou* (火候) is the craft of heat control — knowing when to wait, when to hold, and when to turn off the flame. Each skill is one work discipline drilled into instinct. Follows the `SKILL.md` + `references/` progressive-loading structure.

## Install

```bash
# Install everything into the shared directory (auto-visible to Claude Code / Codex / Kimi Code / Cursor, etc.)
npx skills add BiBoyang/huohou -g -y

# Update later
npx skills update -g -y
```

You can also copy or symlink a single skill directory into `~/.claude/skills/` or any agent's skills directory.

## What's inside

Engineering line: `huohou-plan-first` (before coding) → coding (with `huohou-recover-from-errors` as escort) → `huohou-code-review` (after coding) → `huohou-wrap-up` (shipping). `huohou-collab-mode` is an optional enhanced mode for large tasks.

Content line: `huohou-digest` (intake) → `huohou-polish` (before publishing) → md2wechat (publishing, not in this repo).

| Skill | Purpose | Trigger |
|---|---|---|
| `huohou-plan-first` | Plan before code: root-cause analysis / candidate designs, trade-offs, verification approach; lists open decision points and stops for confirmation | Mandatory before modifying code, implementing features, fixing bugs, or refactoring; read-only review, explanation, and research do not trigger |
| `huohou-recover-from-errors` | Anti-drift error recovery: classify transient vs deterministic failures, re-anchor against the goal, fix root causes not symptoms, hard-stop after repeated failures | Mandatory when tool calls / commands keep failing or stalling |
| `huohou-code-review` | General review workflow and discipline (distilled from deepseek-harness), with Ousterhout's Red Flags checklist | Reviewing PRs/diffs, code review |
| `huohou-wrap-up` | Commit/push/wrap-up/release chain: commit defaults to commit+push, push only pushes; wrap-up covers session log, README sync, and verification; release adds semver bump and tag | `提交` / `推送` / `收尾` / `收尾并发布` |
| `huohou-collab-mode` | Collab mode entry: WORKFLOW.md protocol + topological parallel dispatch + evidence-based acceptance | `协作模式` / `退出协作模式` |
| `huohou-digest` | Research digestion: turns books, codebases, and long articles into structured study notes, with a "knowledge vs habit" gate before anything becomes a skill | "帮我消化/学习/研究 X" |
| `huohou-polish` | Prose polishing: edits by the priority facts > premises > logic > filler > code > boundaries > terminology > tone, preserving original meaning and personal voice; ships a technical-writing checklist (12 questions) and de-AI-flavor rules | "帮我润色/看看这段文字" |
| `huohou-swift-concurrency` | Swift concurrency expert: data-race diagnosis, async/await migration, actor isolation, Swift 6 migration (adopted from [Swift Concurrency Course](https://www.swiftconcurrencycourse.com), synced with upstream v2.3.0, kept in English) | Swift concurrency issues, Swift 6 migration |
| `huohou-rust-expert` | Rust expert: borrow-checker diagnostics (E0502/E0499 etc.), lifetimes, Send/Sync, error handling, async/tokio, unsafe review; understand what the borrow checker protects before applying the minimal safe fix | Rust errors, concurrency, error-handling design |

## Conventions

- Writing meta-rules (fluff test, target-not-script, lists only consolidate) live in `WRITING.md` (Chinese)
- One skill, one job; the description enumerates trigger scenarios and keywords, including colloquial ones
- `SKILL.md` carries the fast path only; details go into `references/`
- Every skill states how "done" is verified
- Update the table above when adding a skill
