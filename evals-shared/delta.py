#!/usr/bin/env python3
"""Cost/latency delta between with_skill and without_skill arms.

Reads benchmark.json (skill-up --baseline artifacts) and reports:
  - skill lift: pass_rate delta (with - without)
  - latency increment: time_seconds delta (absolute seconds + %)
  - token increment: tokens delta — only if the engine reports usage.
    kimi's stream-json has no usage events, so this is usually unavailable;
    in that case a response-length proxy (mean final_message chars,
    with - without, from result.json) is reported instead, clearly labelled.

Exit 0 = report produced; 2 = no benchmark.json found.
"""

import argparse
import glob
import json
import os
import re
import sys


def latest_benchmark(workspace):
    candidates = glob.glob(os.path.join(workspace, "iteration-*", "benchmark.json"))
    candidates += [os.path.join(workspace, "benchmark.json")]
    existing = [c for c in candidates if os.path.isfile(c)]
    if not existing:
        return None, None
    def it_num(p):
        m = re.search(r"iteration-(\d+)", p)
        return int(m.group(1)) if m else -1
    best = max(existing, key=it_num)
    return best, (it_num(best) if it_num(best) > 0 else None)


def response_lengths(workspace, iteration, config):
    """Mean final-response length in chars for one arm, from result.json."""
    path = os.path.join(workspace, f"iteration-{iteration}", "result.json") \
        if iteration else os.path.join(workspace, "result.json")
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    lengths = [len(c.get("response") or "") for c in data.get("case_results", [])
               if c.get("configuration") == config]
    return sum(lengths) / len(lengths) if lengths else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", help="skill-up output dir containing benchmark.json")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON only")
    args = parser.parse_args()

    bench_path, iteration = latest_benchmark(args.workspace)
    if not bench_path:
        print(f"no benchmark.json under {args.workspace}", file=sys.stderr)
        return 2
    with open(bench_path, encoding="utf-8") as f:
        bench = json.load(f)

    summary = bench.get("run_summary", {})
    with_s, without_s = summary.get("with_skill", {}), summary.get("without_skill", {})

    def mean(arm, metric):
        val = arm.get(metric, {})
        return val.get("mean") if isinstance(val, dict) else None

    report = {"benchmark": bench_path, "iteration": iteration}

    lift = None
    pw, pwo = mean(with_s, "pass_rate"), mean(without_s, "pass_rate")
    if pw is not None and pwo is not None:
        lift = round(pw - pwo, 4)
    report["skill_lift_pass_rate"] = lift

    tw, two = mean(with_s, "time_seconds"), mean(without_s, "time_seconds")
    lat_delta = lat_pct = None
    if tw is not None and two is not None:
        lat_delta = round(tw - two, 3)
        lat_pct = round((tw - two) / two * 100, 1) if two else None
    report["latency_delta_seconds"] = lat_delta
    report["latency_delta_percent"] = lat_pct

    kw, kwo = mean(with_s, "tokens"), mean(without_s, "tokens")
    token_available = bool(kw or kwo)
    report["token_delta"] = round(kw - kwo, 1) if token_available else None
    report["token_reported_by_engine"] = token_available

    if not token_available and iteration is not None:
        lw = response_lengths(args.workspace, iteration, "with_skill")
        lwo = response_lengths(args.workspace, iteration, "without_skill")
        if lw is not None and lwo is not None:
            report["response_length_proxy"] = {
                "note": "engine reports no token usage; char-length delta of final responses is a rough output-inflation proxy only",
                "with_skill_mean_chars": round(lw, 1),
                "without_skill_mean_chars": round(lwo, 1),
                "delta_chars": round(lw - lwo, 1),
            }

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    print(f"Benchmark: {bench_path}" + (f" (iteration {iteration})" if iteration else ""))
    print(f"Skill lift (pass_rate with - without): {lift:+.4f}" if lift is not None
          else "Skill lift: n/a")
    if lat_delta is not None:
        pct = f" ({lat_pct:+.1f}%)" if lat_pct is not None else ""
        print(f"Latency increment: {lat_delta:+.3f}s{pct}")
    else:
        print("Latency increment: n/a")
    if token_available:
        print(f"Token increment: {report['token_delta']:+.1f}")
    else:
        print("Token increment: UNAVAILABLE — engine (kimi stream-json) reports no usage")
        proxy = report.get("response_length_proxy")
        if proxy:
            print(f"  proxy: response length {proxy['without_skill_mean_chars']} -> "
                  f"{proxy['with_skill_mean_chars']} chars ({proxy['delta_chars']:+.1f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
