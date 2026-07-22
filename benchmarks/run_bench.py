#!/usr/bin/env python3
"""Run a coding benchmark suite against the local LM Studio server and append
one record to benchmarks/results.jsonl. Stdlib only — no pip installs.

Usage (from repo root, .env filled in):
  python3 benchmarks/run_bench.py \
      --backend-version "LM Studio 0.4.18" --gpu-backend vulkan \
      --context 16384 --quant Q4_K_M --vram-gb 10.2 \
      --notes "first run after setup"

Everything that identifies the *setup* (not just the model) is recorded so any
two rows can be diffed: model+quant, backend+version, context, hardware state.
See benchmarks/README.md for the schema.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "benchmarks" / "results.jsonl"

# Reference API pricing for the $-equivalent column ($/Mtok). Override via CLI.
REF_API_NAME = "claude-sonnet-5"
REF_PRICE_IN = 3.00
REF_PRICE_OUT = 15.00


def load_env():
    env = {}
    envfile = ROOT / ".env"
    if envfile.exists():
        for line in envfile.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def http_json(url, payload=None, timeout=300):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def stream_completion(base, model, prompt, max_tokens, timeout=600):
    """Stream a chat completion; return (text, ttft_s, gen_tokens, gen_s, usage)."""
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.2,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    req = urllib.request.Request(
        f"{base}/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    t0 = time.monotonic()
    ttft = None
    chunks, usage = [], None
    with urllib.request.urlopen(req, timeout=timeout) as r:
        for raw in r:
            raw = raw.decode("utf-8", "replace").strip()
            if not raw.startswith("data: "):
                continue
            raw = raw[6:]
            if raw == "[DONE]":
                break
            obj = json.loads(raw)
            if obj.get("usage"):
                usage = obj["usage"]
            for ch in obj.get("choices", []):
                delta = ch.get("delta", {}).get("content")
                if delta:
                    if ttft is None:
                        ttft = time.monotonic() - t0
                    chunks.append(delta)
    total_s = time.monotonic() - t0
    text = "".join(chunks)
    gen_tokens = (usage or {}).get("completion_tokens")
    gen_s = total_s - (ttft or 0)
    return text, ttft, gen_tokens, gen_s, usage


def extract_code(text):
    # Longest fenced block that looks like code — models sometimes echo the
    # instruction's "```python code block." phrase in prose, producing bogus
    # tiny "blocks"; last-block or first-block heuristics both get fooled.
    # Info string after ``` is matched loosely: models echo prompt phrases
    # there (seen: "```python code block.") and a strict ```python\n misses it.
    blocks = re.findall(r"```[^\n]*\n(.*?)```", text, re.DOTALL)
    code_blocks = [b for b in blocks if "def " in b or "class " in b] or blocks
    return max(code_blocks, key=len) if code_blocks else text


def grade(code, tests):
    prog = code + "\n\n" + tests + "\nprint('__PASS__')\n"
    try:
        p = subprocess.run(
            [sys.executable, "-c", prog], capture_output=True, text=True, timeout=15
        )
        return "__PASS__" in p.stdout, (p.stderr.strip()[-300:] or None)
    except subprocess.TimeoutExpired:
        return False, "timeout"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", default=str(ROOT / "benchmarks/tasks/microeval_v1.json"))
    ap.add_argument("--model", help="override model id (default: LLM_MODEL or first loaded)")
    ap.add_argument("--quant", default="", help="e.g. Q4_K_M (not always in model id)")
    ap.add_argument("--backend-version", default="", help='e.g. "LM Studio 0.4.18"')
    ap.add_argument("--gpu-backend", default="", help="vulkan | rocm | cpu | metal")
    ap.add_argument("--context", type=int, default=0, help="context length configured server-side")
    ap.add_argument("--vram-gb", type=float, default=None, help="observed VRAM use (manual read)")
    ap.add_argument("--power-w", type=float, default=None, help="observed GPU power draw (manual read)")
    ap.add_argument("--hardware-note", default="", help='e.g. "nothing else on GPU"')
    ap.add_argument("--notes", default="")
    ap.add_argument("--max-tokens", type=int, default=1200)
    ap.add_argument("--limit", type=int, default=0,
                    help="run only the first N tasks (harness validation; n_tasks in the record reflects the subset)")
    ap.add_argument("--price-in", type=float, default=REF_PRICE_IN)
    ap.add_argument("--price-out", type=float, default=REF_PRICE_OUT)
    args = ap.parse_args()

    env = load_env()
    host, port = env.get("LLM_HOST"), env.get("LLM_PORT", "1234")
    if not host:
        sys.exit("LLM_HOST not set — copy .env.example to .env first.")
    base = f"http://{host}:{port}"

    model = args.model or env.get("LLM_MODEL")
    if not model:
        model = http_json(f"{base}/v1/models")["data"][0]["id"]
    suite = json.load(open(args.suite))
    if args.limit:
        suite["tasks"] = suite["tasks"][: args.limit]

    print(f"suite={suite['suite']}-{suite['version']}  model={model}  server={base}")
    results, ttfts, tok_rates = [], [], []
    tokens_in = tokens_out = 0
    wall0 = time.monotonic()

    for task in suite["tasks"]:
        prompt = (
            task["prompt"]
            + "\n\nReturn ONLY the code, in a single ```python code block. No explanation."
        )
        try:
            text, ttft, gen_tok, gen_s, usage = stream_completion(
                base, model, prompt, args.max_tokens
            )
        except Exception as e:
            print(f"  {task['id']}: REQUEST ERROR {e}")
            results.append({"id": task["id"], "pass": False, "error": f"request: {e}"})
            continue
        ok, err = grade(extract_code(text), task["tests"])
        results.append({"id": task["id"], "pass": ok, "error": err})
        if ttft:
            ttfts.append(ttft)
        if gen_tok and gen_s > 0:
            tok_rates.append(gen_tok / gen_s)
        if usage:
            tokens_in += usage.get("prompt_tokens", 0)
            tokens_out += usage.get("completion_tokens", 0)
        print(f"  {task['id']}: {'PASS' if ok else 'FAIL'}"
              + (f"  ({gen_tok} tok, {gen_tok/gen_s:.1f} tok/s)" if gen_tok and gen_s > 0 else ""))

    wall = time.monotonic() - wall0
    passed = sum(r["pass"] for r in results)
    total = len(results)
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": model,
        "quant": args.quant or None,
        "backend": {
            "engine": args.backend_version or None,
            "gpu_backend": args.gpu_backend or None,
        },
        "context_length": args.context or None,
        "hardware_note": args.hardware_note or None,
        "suite": {
            "name": suite["suite"],
            "version": suite["version"],
            "n_tasks": total,
        },
        "results": {
            "pass_rate": round(passed / total, 3) if total else None,
            "passed": passed,
            "total": total,
            "tokens_per_sec_gen": round(sum(tok_rates) / len(tok_rates), 1) if tok_rates else None,
            "ttft_s": round(sum(ttfts) / len(ttfts), 2) if ttfts else None,
            "vram_gb": args.vram_gb,
            "power_w": args.power_w,
            "wall_clock_s": round(wall, 1),
            "tokens_in": tokens_in or None,
            "tokens_out": tokens_out or None,
            "api_cost_equiv_usd": round(
                tokens_in / 1e6 * args.price_in + tokens_out / 1e6 * args.price_out, 4
            ) if tokens_in or tokens_out else None,
            "api_cost_ref": REF_API_NAME,
        },
        "per_task": results,
        "notes": args.notes or None,
    }
    with open(RESULTS, "a") as f:
        f.write(json.dumps(record) + "\n")
    print(f"\n{passed}/{total} passed ({record['results']['pass_rate']:.0%})  "
          f"wall={wall:.0f}s  appended to {RESULTS.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
