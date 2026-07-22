#!/usr/bin/env python3
"""Render benchmarks/results.jsonl as a markdown comparison table.

Examples:
  python3 benchmarks/report.py                     # all runs, oldest first
  python3 benchmarks/report.py --last 5            # trend check
  python3 benchmarks/report.py --model qwen        # every run of a model (substring)
  python3 benchmarks/report.py --backend vulkan    # every run on a backend
  python3 benchmarks/report.py --since 2026-08-01
"""
import argparse
import json
from pathlib import Path

RESULTS = Path(__file__).resolve().parent / "results.jsonl"


def fmt(v, suffix=""):
    return f"{v}{suffix}" if v is not None else "—"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", help="substring filter on model name")
    ap.add_argument("--backend", help="substring filter on engine/gpu_backend")
    ap.add_argument("--since", help="YYYY-MM-DD lower bound")
    ap.add_argument("--last", type=int, help="only the N most recent runs")
    ap.add_argument("--suite", help="substring filter on suite name")
    args = ap.parse_args()

    if not RESULTS.exists():
        raise SystemExit("No results yet — run run_bench.py first.")
    rows = [json.loads(l) for l in RESULTS.read_text().splitlines() if l.strip()]

    if args.model:
        rows = [r for r in rows if args.model.lower() in r["model"].lower()]
    if args.backend:
        rows = [r for r in rows if args.backend.lower() in json.dumps(r.get("backend", {})).lower()]
    if args.since:
        rows = [r for r in rows if r["timestamp"][:10] >= args.since]
    if args.suite:
        rows = [r for r in rows if args.suite.lower() in r["suite"]["name"].lower()]
    rows.sort(key=lambda r: r["timestamp"])
    if args.last:
        rows = rows[-args.last:]
    if not rows:
        raise SystemExit("No runs match the filters.")

    hdr = ["date", "model", "quant", "backend", "ctx", "suite",
           "pass", "tok/s", "ttft", "vram", "wall", "$-equiv", "notes"]
    print("| " + " | ".join(hdr) + " |")
    print("|" + "---|" * len(hdr))
    for r in rows:
        res, b = r["results"], r.get("backend", {})
        backend = " ".join(x for x in [b.get("engine"), b.get("gpu_backend")] if x) or "—"
        print("| " + " | ".join([
            r["timestamp"][:16].replace("T", " "),
            r["model"],
            fmt(r.get("quant")),
            backend,
            fmt(r.get("context_length")),
            f'{r["suite"]["name"]}-{r["suite"]["version"]}',
            f'{res["passed"]}/{res["total"]} ({res["pass_rate"]:.0%})' if res.get("pass_rate") is not None else "—",
            fmt(res.get("tokens_per_sec_gen")),
            fmt(res.get("ttft_s"), "s"),
            fmt(res.get("vram_gb"), "GB"),
            fmt(res.get("wall_clock_s"), "s"),
            fmt(res.get("api_cost_equiv_usd"), ""),
            (r.get("notes") or "—")[:60],
        ]) + " |")


if __name__ == "__main__":
    main()
