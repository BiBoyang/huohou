#!/usr/bin/env python3
"""Trigger P/R/F1 report from a skill-up trigger-eval run directory.

Scans <run_dir>/**/session-result.json (written by kimi_engine.py), extracts
which skills were actually activated (native `Skill` tool calls with
arguments.skill), compares against case-id labels (`trigger-pos-*` should
activate, `trigger-neg-*` should not), and prints a confusion matrix with
precision / recall / F1 for the --skill target.

Works on both single-run and iteration-N layouts: it globs to any depth and
keeps the latest session-result per case_id.

Exit code 0 = report produced (regardless of scores); 2 = no usable data.
"""

import argparse
import glob
import json
import os
import sys

POS_PREFIX = "trigger-pos-"
NEG_PREFIX = "trigger-neg-"


def activated_skills(session_result):
    """Return the list of skill names invoked via the native Skill tool."""
    names = []
    for msg in session_result.get("transcript") or []:
        tc = msg.get("tool_call")
        if not tc:
            continue
        if tc.get("name") == "Skill":
            args = tc.get("arguments") or {}
            if isinstance(args, str):
                # some engines JSON-encode arguments; tolerate both shapes
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            skill = args.get("skill") if isinstance(args, dict) else None
            if skill and skill not in names:
                names.append(skill)
    return names


def read_skill_file(session_result, skill):
    """True if the agent Read skills/<skill>/SKILL.md directly (bypassing the
    Skill tool). Both engines do this on protocol-content questions — it is
    substantive activation evidence, reported separately, never counted as
    protocol activation."""
    marker = f"skills/{skill}/SKILL.md"
    for msg in session_result.get("transcript") or []:
        tc = msg.get("tool_call")
        if not tc:
            continue
        if tc.get("name") == "Read":
            args = tc.get("arguments") or {}
            path = str(args.get("file_path") or args.get("path") or "")
            if marker in path:
                return True
    return False


def collect_latest_by_case(run_dir):
    """Map case_id -> session-result path, preferring with_skill and mtime.
    Also returns case dirs that exist without any session-result (e.g.
    timeout-killed runs) so exclusion is never silent."""
    by_case = {}
    no_result = set()
    for case_dir in glob.glob(os.path.join(run_dir, "**", "trigger-*"), recursive=True):
        if not os.path.isdir(case_dir):
            continue
        segs = case_dir.split(os.sep)
        case_id = segs[-1]
        # only count dirs laid out as <...>/<case>/<config>/outputs/...
        configs = glob.glob(os.path.join(case_dir, "*", "outputs"))
        if not configs:
            continue
        results = glob.glob(os.path.join(case_dir, "*", "outputs", "agent", "run", "session-result.json"))
        if not results:
            no_result.add(case_id)
            continue
        # prefer with_skill arm when present (trigger evals are with_skill-only)
        with_skill = [p for p in results if "with_skill" in p]
        pool = with_skill or results
        path = max(pool, key=os.path.getmtime)
        mtime = os.path.getmtime(path)
        prev = by_case.get(case_id)
        if prev is None or mtime > prev[0]:
            by_case[case_id] = (mtime, path)
    return {cid: p for cid, (_, p) in by_case.items()}, no_result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dirs", nargs="+",
                        help="skill-up output dir(s) — single run or iteration-N; "
                             "same case in multiple dirs resolves to the newest")
    parser.add_argument("--skill", required=True, help="target skill name, e.g. huohou-code-review")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON only")
    args = parser.parse_args()

    cases = {}
    excluded = set()
    for run_dir in args.run_dirs:
        found, no_result = collect_latest_by_case(run_dir)
        excluded |= no_result
        for cid, path in found.items():
            mtime = os.path.getmtime(path)
            prev = cases.get(cid)
            if prev is None or mtime > prev[0]:
                cases[cid] = (mtime, path)
    cases = {cid: p for cid, (_, p) in cases.items()}
    if not cases:
        print(f"no session-result.json found under {args.run_dir}", file=sys.stderr)
        return 2

    rows, unlabeled = [], []
    for case_id in sorted(cases):
        if case_id.startswith(POS_PREFIX):
            should = True
        elif case_id.startswith(NEG_PREFIX):
            should = False
        else:
            unlabeled.append(case_id)
            continue
        with open(cases[case_id], encoding="utf-8") as f:
            result = json.load(f)
        activated = activated_skills(result)
        rows.append({
            "case_id": case_id,
            "should_trigger": should,
            "activated": args.skill in activated,
            "activated_skills": activated,
            "read_skill_file": read_skill_file(result, args.skill),
            "exit_code": result.get("exit_code"),
            "path": cases[case_id],
        })

    tp = sum(r["should_trigger"] and r["activated"] for r in rows)
    fn = sum(r["should_trigger"] and not r["activated"] for r in rows)
    fp = sum(not r["should_trigger"] and r["activated"] for r in rows)
    tn = sum(not r["should_trigger"] and not r["activated"] for r in rows)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    if args.json:
        print(json.dumps({
            "skill": args.skill, "run_dirs": args.run_dirs,
            "excluded_no_result": sorted(excluded),
            "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
            "precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4),
            "rows": rows, "unlabeled": unlabeled,
        }, ensure_ascii=False, indent=2))
        return 0

    print(f"Target skill: {args.skill}")
    print(f"Cases: {len(rows)} labeled, {len(unlabeled)} unlabeled (skipped)")
    if unlabeled:
        print("  unlabeled:", ", ".join(unlabeled))
    if excluded:
        print(f"EXCLUDED: {len(excluded)} case(s) without session-result (timeout-killed): "
              + ", ".join(sorted(excluded)))
    print(f"\nConfusion: TP={tp} FP={fp} FN={fn} TN={tn}")
    print(f"Precision={precision:.3f}  Recall={recall:.3f}  F1={f1:.3f}\n")
    for r in rows:
        verdict = "OK " if r["should_trigger"] == r["activated"] else "MISS"
        expect = "should" if r["should_trigger"] else "should-not"
        others = [s for s in r["activated_skills"] if s != args.skill]
        note = f" (routed to: {', '.join(others)})" if others else ""
        if r["read_skill_file"]:
            note += " [read skill file directly — substantive, not protocol activation]"
        print(f"  [{verdict}] {r['case_id']}: {expect}, activated={r['activated']}{note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
