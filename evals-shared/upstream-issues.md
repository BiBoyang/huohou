# skill-up 上游问题（已发布）

> 产生于 2026-09-19 触发评测全量跑（9 skill × 10 case，kimi + claude 双 custom engine）。
> 前置核验已完成（2026-09-19）：open issues（12 条）无重叠；closed 最近 100 条无重叠
> （唯一关键词命中 #260 为 judge prompt 加固，无关）；huohou 仓库已确认为 public，
> 路径引用有效。证据已内联正文，路径仅辅助。组织方式：先 issue 后 PR。

---

## Issue 1 — 已发布为 #263

**Title:** Case timeout kills custom engine before it can flush its session-result, losing all evaluation data for that case

**（备中文：case 超时强杀 custom engine，session-result 来不及落盘，该 case 评测数据全部丢失）**

### Minimal reproduction

1. Configure a custom engine (`transport: local`, `response_format: session_result`) whose adapter writes the SessionResult JSON to `${output_file}` **after** the child CLI process exits.
2. Create a case whose prompt makes the agent do real work (e.g. a heavy research task), with `cases.defaults.timeout_seconds: 180`.
3. Run `skill-up run evals/eval.yaml`.
4. Observe: the run fails with `custom engine run failed: context deadline exceeded (case timeout 180s ...)`, and under `<output-dir>/iteration-1/<case>/<config>/outputs/agent/run/` only `messages.json` exists — no `session-result.json`.

### Expected vs actual

- **Expected:** on case timeout, the engine process gets a chance to flush a partial/timeout-marked result (e.g. SIGTERM with a grace window, or the harness synthesizes a timeout SessionResult). At minimum, the docs should state that a timed-out custom-engine case yields no transcript at all.
- **Actual:** the engine process is killed outright; every trace of the agent run is lost. For trigger-evaluation use cases this is especially costly: skill-activation events happen in the first turns and are already available, but they die with the process.

### Environment

- skill-up: local build `dev-fix253` (upstream main + fix for #253), darwin/arm64 (macOS 15)
- engine: custom local transport (kimi and Claude Code adapters, both show the behavior)
- first hit: `huohou` repo trigger-eval batch, 2026-09-19

### Our workaround

Action-free prompts for heavy tasks ("assume the repo is already cloned, describe your process") + per-case `timeout_seconds` bumps. Fragile — any prompt that slips through silently loses its data point.

### Fix ownership & PR outline

skill-up side (runtime/process management, not engine side). PR sketch, no code:
- In the custom-engine local runner, on deadline expiry send SIGTERM first, wait a short grace period (configurable, e.g. 5–10s), then SIGKILL. Most adapter scripts can write a timeout-marked result in that window.
- Alternative (smaller): when the deadline fires and no output file exists, synthesize a SessionResult with `exit_code: 124` and `stderr: "case timeout"` so downstream tooling at least has a record.
- Touch points: `internal/agent/custom_local.go` exec path + wherever the case-level `context.WithTimeout` is enforced. Needs verification against both `local` and `http` transports.

### Evidence (inlined — do not depend on repo access)

Console output from the failing run (2026-09-19):

```console
[ERROR] case trigger-pos-digest-repo: agent execution failed: custom engine run failed:
context deadline exceeded (case timeout 180s via cases.defaults.timeout_seconds)
```

Post-mortem directory listing (only the input was persisted; the adapter never got to write `${output_file}`):

```console
$ ls <output-dir>/iteration-1/trigger-pos-digest-repo/with_skill/outputs/agent/run/
messages.json
$ # session-result.json absent — the agent's transcript (including early-turn
$ # Skill activation events) died with the killed process
```

Same shape reproduced for two more cases (`trigger-pos-digest-book` at 180s and 300s, `trigger-neg-unrelated`) before the action-free-prompt workaround.

Auxiliary (works only if the huohou repo is reachable): first-run residue under the gitignored `huohou-digest-triggers-workspace/` at `github.com/BiBoyang/huohou`.

---

## Issue 2 — 已发布为 #264

**Title:** Rerunning a single case with `--include-case-name` into a non-empty output workspace reports PASS but writes no fresh artifacts

**（备中文：对非空输出目录用 --include-case-name 单 case 重跑，报告 PASS 但不落任何新产物）**

### Minimal reproduction

1. Run `skill-up run evals/eval.yaml --output-dir ws` (creates `ws/iteration-1/...` with full artifacts).
2. Modify the case or its prompt, then rerun one case into the same workspace:
   `skill-up run evals/eval.yaml --include-case-name "<case>" --output-dir ws`
3. Observe: console prints `✅ [1/1] <case>: PASS`, but `ws/iteration-1/<case>/.../session-result.json` is unchanged (old mtime). `messages.json` does get rewritten. Rerunning into a fresh `--output-dir` works correctly.

### Expected vs actual

- **Expected:** a rerun either appends a new `iteration-N` or overwrites the case's artifacts with the new run's; console success should imply fresh artifacts.
- **Actual:** the run reports success while the on-disk session-result stays stale (or, when the previous run was killed, stays absent) — silently breaking any downstream tool that reads the workspace.

### Environment

- same as Issue 1 (skill-up dev-fix253, custom local engine, darwin/arm64)
- hit 3 times in one day during single-case reruns

### Our workaround

Rerun single cases into a clean `--output-dir`, then aggregate: our `trigger_report.py` accepts multiple run directories and resolves a case by newest mtime.

### Fix ownership & PR outline

skill-up side (runner output/iteration bookkeeping). PR sketch, no code:
- Diagnose the interaction between the existing-`iteration-1` discovery and the artifact write path for a filtered rerun (suspect: case-dir reuse skips or misroutes the agent-run copy step while `messages.json` is written unconditionally).
- Likely minimal fix: treat any rerun into an existing workspace as `iteration-<last+1>` (consistent with documented `--iteration 0` auto-append semantics) instead of merging into `iteration-1`.
- Needs a regression test: run full → rerun one case → assert new session-result mtime.

### Evidence (inlined — do not depend on repo access)

Reproduction transcript (2026-09-19, macOS arm64, skill-up dev-fix253):

```console
$ stat -f "%m %N" .../iteration-1/trigger-pos-terse/with_skill/outputs/agent/run/session-result.json
1789808917 .../iteration-1/trigger-pos-terse/with_skill/outputs/agent/run/session-result.json

$ skill-up run evals/eval-triggers.yaml --include-case-name "trigger-pos-terse" --output-dir <same-workspace>
📋 Results: 1 passed, 0 failed, 0 errors

$ stat -f "%m %N" .../iteration-1/trigger-pos-terse/with_skill/outputs/agent/run/session-result.json
1789808917 .../iteration-1/trigger-pos-terse/with_skill/outputs/agent/run/session-result.json
# ^ identical mtime: the rerun reported PASS but wrote nothing for the case
```

Directory shape from the timeout variant (Issue 1 overlap — killed engine leaves a half-written case dir):

```console
$ ls <workspace>/iteration-1/trigger-pos-digest-repo/with_skill/outputs/agent/run/
messages.json            # input only
$ # no session-result.json — nothing downstream can grade this case
```

Auxiliary (works only if the huohou repo is reachable): the gitignored `huohou-*-triggers-workspace/` dirs under `github.com/BiBoyang/huohou`.
