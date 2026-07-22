# Benchmarks

Reusable benchmark infrastructure for comparing **setups**, not just models —
"did Vulkan → ROCm help, holding the model constant?", "did the LM Studio
upgrade change tok/s for the same model+quant?".

## Files

- `results.jsonl` — **append-only** results log. One JSON record per benchmark
  run. Never overwrite or edit past rows; corrections go in a new run's `notes`.
- `run_bench.py` — runs a task suite against the LM Studio server (address from
  `../.env`), grades results, measures speed, appends one record.
- `report.py` — renders `results.jsonl` as a markdown table, filterable by
  model / backend / suite / date, or `--last N` for trend checks.
- `tasks/microeval_v1.json` — task suite. **Frozen once used**: never edit an
  existing suite file (that would silently break comparability); create
  `microeval_v2.json` and bump `version` instead.

## Record schema (one line of results.jsonl)

```jsonc
{
  "timestamp": "2026-07-21T20:00:00+00:00",   // UTC ISO-8601
  "model": "qwen2.5-coder-14b-instruct",       // id as served by LM Studio
  "quant": "Q4_K_M",                           // null if unknown
  "backend": {
    "engine": "LM Studio 0.4.18",              // app + version (llama.cpp build if known)
    "gpu_backend": "vulkan"                    // vulkan | rocm | cpu | metal
  },
  "context_length": 16384,                     // configured server-side
  "hardware_note": "nothing else on GPU",      // anything that varies run-to-run
  "suite": { "name": "microeval", "version": "v1", "n_tasks": 10 },
  "results": {
    "pass_rate": 0.8, "passed": 8, "total": 10,
    "tokens_per_sec_gen": 32.5,                // mean generation speed across tasks
    "ttft_s": 1.4,                             // mean time-to-first-token
    "vram_gb": 10.2,                           // manual read (LM Studio UI / Task Manager); null if not taken
    "power_w": null,                           // manual read if measurable
    "wall_clock_s": 412.0,
    "tokens_in": 4100, "tokens_out": 9800,
    "api_cost_equiv_usd": 0.159,               // what the same tokens would cost on the reference API
    "api_cost_ref": "claude-sonnet-5"          // pricing reference used
  },
  "per_task": [ { "id": "lru-cache", "pass": true, "error": null } ],
  "notes": "first run after LM Studio upgrade"
}
```

Fields that can't be measured from the Mac (VRAM, power) are passed manually
via `--vram-gb` / `--power-w` — read them off the Windows box (LM Studio's
server page or Task Manager → GPU) during the run. `null` means "not measured",
never "zero".

## Comparability rules

1. Same suite name+version = comparable pass rates. Different suite = different
   column, never mix.
2. Record the backend/version on **every** run, even if it "hasn't changed" —
   silent upgrades are exactly what this exists to catch.
3. One variable at a time when possible (model OR backend OR context), noted in
   `notes`.

## Suites

- `microeval-v1` (current): 10 Python tasks — parsing, algorithms, data
  structures, one class-design task. Small enough to run in minutes on a local
  14B model; discriminative enough to rank setups. A full
  [Aider polyglot](https://github.com/Aider-AI/aider/tree/main/benchmark) run
  is the planned heavier suite once the setup stabilizes; its scores would be
  logged with `suite.name = "aider-polyglot"` alongside microeval rows.
