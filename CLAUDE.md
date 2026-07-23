# local-llm-lab

Claude Code → LAN LM Studio (Bionic) local-model routing + benchmark infra.
Read `README.md` for setup, `DEVLOG.md` for history, `benchmarks/README.md`
for the results schema. Server details (IP, model) live in `.env` (gitignored).

## Server management (Windows box, over SSH)

- SSH alias: `ssh winbox` (dedicated key; never modify the user's other keys).
- Model control: `lms ps` / `lms load <model> --context-length N --parallel 1 --gpu <ratio> -y` / `lms unload --all`.
- The box runs **LM Studio Bionic** (agent app) — no GUI server tab. All
  server config via `lms` CLI or `~\.lmstudio\.internal\http-server-config.json`
  (LAN bind: `networkInterface: "0.0.0.0"`, persisted; JIT loading toggle too).
- Bionic's context auto-fit floor: `~\.lmstudio\apps\bionic\.internal\settings.json`
  → `localModels.autoFitMinContextLength` (raised to 32768; if loads clamp to
  16384 again, check this first).
- **Cold-boot gotcha:** if models won't load and `lms runtime survey` shows no
  GPU, Bionic raced the AMD Vulkan driver at login. Fix:
  `schtasks /run /tn RestartBionic` (task already exists on the box), wait
  ~20s, re-survey.
- Windows is **pt-BR locale**: never use English group/account names in
  commands (use SIDs, e.g. `*S-1-5-32-544`); `ping` is firewall-blocked —
  probe TCP instead.

## Benchmark protocol (IMPORTANT — learned the hard way)

1. **Unload every other model first**: `ssh winbox "lms unload --all"`, then
   load ONLY the target model explicitly. JIT loading will otherwise load a
   second model alongside (27GB on a 16GB card happened) and poison the run.
2. **Quiet GPU**: no interactive Claude Code sessions against the server while
   a benchmark runs — their 25-30K prefills monopolize the engine.
3. Always pass `--model` explicitly to `run_bench.py` — never trust
   auto-detect (JIT makes "first model in /v1/models" arbitrary).
4. Record backend + version flags on every run even if unchanged.
5. `results.jsonl` is append-only. Suite files are frozen once used — new
   tasks go in a new suite version.
6. Model-side config that made runs comparable so far: `--parallel 1`,
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

Never commit: IPs, `.env`, `.claude/settings.local.json`, personal paths.
`.env.example` uses placeholders only.
