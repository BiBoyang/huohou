#!/usr/bin/env python3
"""Flaky Rate and Error Rate from skill-up --iteration N artifacts.

Two separate ledgers per case (optionally filtered to one configuration arm),
collected across iteration-*/result.json:

  - Flaky Rate: cases whose non-ERROR statuses swing (both PASS and FAIL
    seen, >= 2 non-ERROR runs). ERROR runs are excluded from this judgement —
    an ERROR is usually infra noise (rate limit, timeout), not skill
    instability, and mixing it in both inflates and distorts the rate.
  - Error Rate: ERROR runs / total runs, global and per-case. A case that is
    all-ERROR shows up here instead of polluting the flaky ledger.

Exit 0 = report produced; 2 = no case has >= 2 non-ERROR runs and no ERRORs.
"""

import argparse
import glob
import json
import os
import re
import sys
from collections import defaultdict

STATUS_ICON = {"PASS": "✓", "FAIL": "✗", "ERROR": "!"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", help="skill-up output dir containing iteration-*/result.json")
    parser.add_argument("--config", default="with_skill", help="configuration arm to measure (default with_skill)")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON only")
    args = parser.parse_args()

    # (case_id, iteration) -> status, per requested config arm
    runs = defaultdict(dict)
    iter_dirs = sorted(
        glob.glob(os.path.join(args.workspace, "iteration-*")),
        key=lambda d: int(re.search(r"iteration-(\d+)$", d).group(1)),
    )
    for it in iter_dirs:
        result_file = os.path.join(it, "result.json")
        if not os.path.isfile(result_file):
            continue
        with open(result_file, encoding="utf-8") as f:
            data = json.load(f)
        it_num = int(re.search(r"iteration-(\d+)$", it).group(1))
        for case in data.get("case_results", []):
            if args.config and case.get("configuration") != args.config:
                continue
            runs[case["case_id"]][it_num] = case.get("status", "UNKNOWN")

    sequences = {cid: [by_iter[i] for i in sorted(by_iter)] for cid, by_iter in runs.items()}

    flaky, eligible = {}, {}
    for cid, seq in sequences.items():
        non_error = [s for s in seq if s != "ERROR"]
        if len(non_error) >= 2:
            eligible[cid] = seq
            if len(set(non_error)) > 1:
                flaky[cid] = seq

    total_runs = sum(len(seq) for seq in sequences.values())
    error_runs = sum(seq.count("ERROR") for seq in sequences.values())
    flaky_rate = len(flaky) / len(eligible) if eligible else 0.0
    error_rate = error_runs / total_runs if total_runs else 0.0

    if not eligible and error_runs == 0:
        print(f"no case has >= 2 non-ERROR iterations under config '{args.config}' in {args.workspace}",
              file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps({
            "workspace": args.workspace, "config": args.config,
            "iterations": [int(re.search(r'iteration-(\d+)$', d).group(1)) for d in iter_dirs],
            "flaky_rate": round(flaky_rate, 4),
            "flaky_eligible_cases": len(eligible),
            "flaky_cases": sorted(flaky),
            "error_rate": round(error_rate, 4),
            "error_runs": error_runs,
            "total_runs": total_runs,
            "sequences": sequences,
        }, ensure_ascii=False, indent=2))
        return 0

    print(f"Config: {args.config} | iterations found: {len(iter_dirs)}")
    print(f"Flaky Rate: {flaky_rate:.3f} ({len(flaky)}/{len(eligible)} PASS/FAIL-swinging cases)")
    print(f"Error Rate: {error_rate:.3f} ({error_runs}/{total_runs} runs errored — infra noise ledger)\n")
    for cid in sorted(sequences):
        seq = sequences[cid]
        icons = "".join(STATUS_ICON.get(s, "?") for s in seq)
        tags = []
        if cid in flaky:
            tags.append("<-- FLAKY")
        if "ERROR" in seq:
            tags.append(f"<-- {seq.count('ERROR')} ERROR run(s)")
        print(f"  {cid:40s} {icons} {'/'.join(seq)} {' '.join(tags)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
