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


def collect_latest_by_case(run_dir):
    """Map case_id -> session-result path, preferring with_skill and mtime."""
    by_case = {}
    for path in glob.glob(os.path.join(run_dir, "**", "session-result.json"), recursive=True):
        parent = os.path.basename(os.path.dirname(path))          # run dir name
        case_dir = os.path.dirname(os.path.dirname(path))
        # Layout: <case>/<config>/outputs/agent/run/session-result.json
        # or      <iteration>/<case>/<config>/outputs/agent/run/...
        config = parent  # "run"; config dir is one level above outputs
        segs = path.split(os.sep)
        try:
            cfg_idx = len(segs) - 1 - segs[::-1].index("outputs") - 1
            cfg_name = segs[cfg_idx]
        except ValueError:
            continue
        if "without_skill" in cfg_name:
            continue  # trigger evals are with_skill-only by design
        case_id = segs[cfg_idx - 1]
        mtime = os.path.getmtime(path)
        prev = by_case.get(case_id)
        if prev is None or mtime > prev[0]:
            by_case[case_id] = (mtime, path)
    return {cid: p for cid, (_, p) in by_case.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", help="skill-up output dir (single run or iteration-N)")
    parser.add_argument("--skill", required=True, help="target skill name, e.g. huohou-code-review")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON only")
    args = parser.parse_args()

    cases = collect_latest_by_case(args.run_dir)
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
            "skill": args.skill, "run_dir": args.run_dir,
            "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
            "precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4),
            "rows": rows, "unlabeled": unlabeled,
        }, ensure_ascii=False, indent=2))
        return 0

    print(f"Target skill: {args.skill}")
    print(f"Cases: {len(rows)} labeled, {len(unlabeled)} unlabeled (skipped)")
    if unlabeled:
        print("  unlabeled:", ", ".join(unlabeled))
    print(f"\nConfusion: TP={tp} FP={fp} FN={fn} TN={tn}")
    print(f"Precision={precision:.3f}  Recall={recall:.3f}  F1={f1:.3f}\n")
    for r in rows:
        verdict = "OK " if r["should_trigger"] == r["activated"] else "MISS"
        expect = "should" if r["should_trigger"] else "should-not"
        others = [s for s in r["activated_skills"] if s != args.skill]
        note = f" (routed to: {', '.join(others)})" if others else ""
        print(f"  [{verdict}] {r['case_id']}: {expect}, activated={r['activated']}{note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
