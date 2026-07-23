# local-llm-lab

Claude Code → LAN LM Studio local-model routing + benchmark infra.
Read `README.md` for setup, `benchmarks/README.md` for the results schema.
Server details (IP, model) live in `.env` (gitignored).

Machine-specific server management (SSH alias, OS quirks, boot-race fixes)
lives in `CLAUDE.local.md` — gitignored, not part of the public repo, since
it's this contributor's personal box, not something the project depends on.

## Benchmark protocol (IMPORTANT — learned the hard way)

1. **One run at a time, foreground, to completion.** Never launch a benchmark
   in the background or run two in parallel — a second run on the same server
   contends for the GPU and poisons both results (see rule 2). Start the
   script, wait for it to exit, THEN read and evaluate the output. Don't do
   other work or spend tokens polling while it runs — it's a single blocking
   step, not a background job.
2. **Unload every other model first**, then load ONLY the target model
   explicitly. JIT loading will otherwise load a second model alongside (27GB
   on a 16GB card happened) and poison the run.
3. **Quiet GPU**: no interactive Claude Code sessions against the server while
   a benchmark runs — their 25-30K prefills monopolize the engine.
4. Always pass `--model` explicitly to `run_bench.py` — never trust
   auto-detect (JIT makes "first model in /v1/models" arbitrary).
5. Record backend + version flags on every run even if unchanged.
6. `results.jsonl` is append-only. Suite files are frozen once used — new
   tasks go in a new suite version.
7. Model-side config that made runs comparable so far: `--parallel 1`,
   explicit `--context-length`, note `--gpu` ratio in `hardware_note`.

## Model facts (as of 2026-07-23)

- `qwen/qwen3-coder-30b` Q4_K_M: daily driver. Tool-calls correctly. 18.6GB →
  partial CPU offload; decode ~34 tok/s; prefill ~130-170 tok/s (the
  interactive bottleneck: first Claude Code turn = 2-4 min).
- `qwen2.5-coder-14b-instruct` Q4_K_M: benchmarks well (8/10) but its GGUF
  template emits tool calls as `<tools>` TEXT — unusable for agents. Do not
  point Claude Code at it.
- `openai/gpt-oss-20b`: candidate (13GB, fully VRAM-resident, tool-trained) —
  pending tool-call smoke test + benchmark.
- Prompt > context ⇒ **silent empty response** (no error). Looks like infinite
  hang in Claude Code.

## Public repo rules

Never commit: IPs, `.env`, `.claude/settings.local.json`, `CLAUDE.local.md`,
`DEVLOG.md`, personal paths. `.env.example` uses placeholders only.
