#!/usr/bin/env python3
"""Self-regression test for the eval tooling itself (a3's discipline: the
evaluator must also be tested). All offline, zero API cost.

Fixtures under fixtures/:
  - bad-skill: a skill with exactly four planted lint problems plus one
    clean reference (no-false-positive guard). If a lint change stops
    catching any of the four, or starts flagging the clean one, this fails.

Synthetic in-memory fixtures cover trigger activation detection and the
flaky/error two-ledger semantics.

Exit 0 = all assertions hold; 1 = tooling regression.
"""

import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import flaky  # noqa: E402
import lint_skill  # noqa: E402
import trigger_report  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f" — {detail}" if detail and not ok else ""))


def test_lint_fixture():
    findings = lint_skill.lint_skill(FIXTURES / "bad-skill")
    by_check = {}
    for f in findings:
        by_check.setdefault(f["check"], []).append(f["message"])

    check("lint catches name/dir mismatch",
          any("wrong-name-on-purpose" in m for m in by_check.get("name-matches-dir", [])))
    check("lint catches missing referenced file",
          any("ghost-file.md" in m for m in by_check.get("referenced-file-exists", [])))
    check("lint catches frontmatter secret (sk-)",
          any("openai-style-key" in m for m in by_check.get("secret-scan", [])))
    check("lint catches body secret literal (api_key)",
          any("assigned-secret-literal" in m for m in by_check.get("secret-scan", [])))
    check("lint does NOT flag the existing real-file.md",
          not any("real-file.md" in m for m in by_check.get("referenced-file-exists", [])),
          str(by_check.get("referenced-file-exists", [])))

    real_skills = sorted(p for p in FIXTURES.parent.parent.glob("huohou-*")
                         if p.is_dir() and not p.name.endswith("-workspace"))
    clean = [p.name for p in real_skills if lint_skill.lint_skill(p)]
    check("lint leaves all 9 real skills clean", not clean, f"flagged: {clean}")


def test_activation_detection():
    pos = {"transcript": [
        {"role": "tool_call", "tool_call": {"id": "t1", "name": "Skill",
                                            "arguments": {"skill": "huohou-x", "args": "a"}}},
    ]}
    neg_routed = {"transcript": [
        {"role": "tool_call", "tool_call": {"id": "t2", "name": "Skill",
                                            "arguments": {"skill": "huohou-other"}}},
    ]}
    legacy_flat = {"transcript": [
        {"role": "assistant", "content": "text"},
        {"role": "tool", "content": "Skill loaded"},  # old flat shape, no tool_call
    ]}
    str_args = {"transcript": [
        # defensive: arguments arriving as a JSON string
        {"role": "tool_call", "tool_call": {"name": "Skill",
                                            "arguments": "{\"skill\": \"huohou-x\"}"}},
    ]}
    check("activation: Skill call with dict args detected",
          trigger_report.activated_skills(pos) == ["huohou-x"])
    check("activation: sibling skill call not target",
          trigger_report.activated_skills(neg_routed) == ["huohou-other"])
    check("activation: legacy flat transcript -> no activation, no crash",
          trigger_report.activated_skills(legacy_flat) == [])
    check("activation: string-encoded arguments tolerated",
          "huohou-x" in trigger_report.activated_skills(str_args))

    read_path = {"transcript": [
        # engine read the SKILL.md directly instead of calling the Skill tool
        {"role": "tool_call", "tool_call": {"name": "Read",
                                            "arguments": {"file_path": "/ws/skills/huohou-x/SKILL.md"}}},
    ]}
    read_other = {"transcript": [
        {"role": "tool_call", "tool_call": {"name": "Read",
                                            "arguments": {"file_path": "/ws/skills/huohou-x/references/a.md"}}},
    ]}
    check("substantive: direct Read of skills/<target>/SKILL.md detected",
          trigger_report.read_skill_file(read_path, "huohou-x"))
    check("substantive: Read of other files not misread as SKILL.md access",
          not trigger_report.read_skill_file(read_other, "huohou-x"))


def test_flaky_ledgers():
    tmp = Path(tempfile.mkdtemp(prefix="flaky-selftest-"))
    try:
        seqs = {
            "stable": ["PASS", "PASS"],
            "swinger": ["PASS", "FAIL"],
            "all-error": ["ERROR", "ERROR"],
            "mixed": ["ERROR", "PASS", "FAIL"],
        }
        for case, statuses in seqs.items():
            for i, status in enumerate(statuses, start=1):
                it_dir = tmp / f"iteration-{i}"
                it_dir.mkdir(exist_ok=True)
                result = it_dir / "result.json"
                data = json.loads(result.read_text()) if result.exists() \
                    else {"case_results": []}
                data["case_results"].append(
                    {"case_id": case, "status": status, "configuration": "with_skill"})
                result.write_text(json.dumps(data))

        import subprocess
        proc = subprocess.run(
            [sys.executable, str(Path(flaky.__file__)), str(tmp), "--json"],
            capture_output=True, text=True)
        out = json.loads(proc.stdout)

        check("flaky: swinger and mixed flagged, stable not",
              set(out["flaky_cases"]) == {"swinger", "mixed"},
              str(out["flaky_cases"]))
        check("flaky: all-error case excluded from eligible denominator",
              out["flaky_eligible_cases"] == 3, str(out["flaky_eligible_cases"]))
        check("flaky: error ledger counts 3 ERROR runs of 9",
              out["error_runs"] == 3 and out["total_runs"] == 9,
              f"{out['error_runs']}/{out['total_runs']}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_claude_eval_home_cleanup_on_crash():
    """Credentials copied into the per-case home must not survive a crash."""
    import claude_engine

    tmp = Path(tempfile.mkdtemp(prefix="claude-cleanup-selftest-"))
    try:
        ws = tmp / "ws"
        ws.mkdir()
        input_json = tmp / "input.json"
        input_json.write_text(json.dumps({
            "workspace": str(ws),
            "messages": [{"role": "user", "content": "hi"}],
            "timeout_seconds": 5,
        }))
        output_json = tmp / "out.json"

        orig_run = claude_engine.subprocess.run
        orig_argv = sys.argv

        def simulated_crash(*a, **k):
            raise RuntimeError("simulated mid-run crash")

        claude_engine.subprocess.run = simulated_crash
        sys.argv = ["claude_engine.py", "--input", str(input_json),
                    "--output", str(output_json)]
        raised = False
        try:
            try:
                claude_engine.main()
            except RuntimeError:
                raised = True
            leaked = (ws / claude_engine.EVAL_HOME_NAME).exists()
        finally:
            claude_engine.subprocess.run = orig_run
            sys.argv = orig_argv

        check("claude: engine crash propagates (test validity)", raised)
        check("claude: credential home removed even after crash", not leaked,
              f"{ws / claude_engine.EVAL_HOME_NAME} still on disk")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_rubric_read_is_shadow_not_activation():
    """Rubric definition, executable: a Read of skills/<t>/SKILL.md is a
    shadow-use signal only — it must NOT count as protocol activation nor
    reduce recall (an unlabeled-Read positive stays an FN)."""
    import subprocess as sp
    tmp = Path(tempfile.mkdtemp(prefix="rubric-selftest-"))
    try:
        d = tmp / "run" / "trigger-pos-readonly" / "with_skill" / "outputs" / "agent" / "run"
        d.mkdir(parents=True)
        json.dump({"exit_code": 0, "transcript": [
            {"role": "tool_call", "tool_call": {"name": "Read",
             "arguments": {"path": "skills/huohou-x/SKILL.md"}}},
            {"role": "assistant", "content": "answered from the doc"},
        ]}, open(d / "session-result.json", "w"))
        proc = sp.run([sys.executable, str(Path(trigger_report.__file__)),
                       str(tmp / "run"), "--skill", "huohou-x", "--json"],
                      capture_output=True, text=True)
        out = json.loads(proc.stdout)
        row = out["rows"][0]
        check("rubric: Read path is not protocol activation", row["activated"] is False)
        check("rubric: Read path lights the shadow signal", row["read_skill_file"] is True)
        check("rubric: Read path gives no recall relief (still FN)",
              out["confusion"] == {"tp": 0, "fp": 0, "fn": 1, "tn": 0},
              str(out["confusion"]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_claude_config_invariant():
    """Every eval-triggers-claude.yaml must differ from its kimi twin ONLY in
    the engine name and adapter path lines — anything else is config drift
    (first catch: a stale case list after a relabel)."""
    import difflib
    repo = FIXTURES.parent.parent
    allowed = ("name: kimi", "name: claude", "kimi_engine.py", "claude_engine.py")
    claude_cfgs = sorted(repo.glob("huohou-*/evals/eval-triggers-claude.yaml"))
    check("config invariant: claude configs exist", len(claude_cfgs) >= 4,
          f"found {len(claude_cfgs)}")
    for cfg in claude_cfgs:
        kimi_cfg = cfg.with_name("eval-triggers.yaml")
        diff_lines = [l for l in difflib.unified_diff(
            kimi_cfg.read_text().splitlines(), cfg.read_text().splitlines(), lineterm="")
            if l[:1] in "<>" and not any(a in l for a in allowed)]
        check(f"config invariant: {cfg.parent.parent.name}", not diff_lines,
              "; ".join(diff_lines[:3]))


def main():
    print("lint fixture assertions:")
    test_lint_fixture()
    print("activation detection assertions:")
    test_activation_detection()
    print("flaky ledger assertions:")
    test_flaky_ledgers()
    print("claude credential-cleanup assertions:")
    test_claude_eval_home_cleanup_on_crash()
    print("rubric (shadow-use) assertions:")
    test_rubric_read_is_shadow_not_activation()
    print("claude config invariant assertions:")
    test_claude_config_invariant()
    failed = [r for r in RESULTS if not r[1]]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} assertions passed")
    if failed:
        for name, _, detail in failed:
            print(f"  REGRESSION: {name} {detail}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
