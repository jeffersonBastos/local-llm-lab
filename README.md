# local-llm-lab

Run [Claude Code](https://code.claude.com) against a **fully local model** served
by [LM Studio](https://lmstudio.ai) on another machine on your LAN — plus
reusable benchmark infrastructure to measure whether your setup changes
(model, quantization, backend, versions) actually help.

## Architecture

```
┌───────────────────────┐        LAN         ┌──────────────────────────┐
│ Dev machine           │  ─────────────────▶│ Inference box            │
│ Claude Code (agent)   │  Anthropic-compat   │ LM Studio server         │
│ this repo, git, IDE   │  POST /v1/messages  │ GGUF model on GPU        │
└───────────────────────┘                     └──────────────────────────┘
```

Any OpenAI/Anthropic-compatible server works the same way, on any OS or
hardware — point `.env` at your own setup.

## How it works

Claude Code natively supports third-party backends via `ANTHROPIC_BASE_URL`,
and LM Studio (≥ 0.4.1) natively serves the Anthropic Messages API at
`/v1/messages` — so they connect **directly, no proxy or shim**. The config
lives in the project's `.claude/settings.local.json` (gitignored), so only
sessions started inside this repo use the local model; everything else on the
machine keeps using the normal Anthropic API.

Two gotchas the setup handles for you:

- **KV-cache busting**: Claude Code prepends a dynamic attribution block to the
  system prompt, which invalidates the local server's prompt cache every turn
  (massive slowdown). Fixed with `CLAUDE_CODE_ATTRIBUTION_HEADER=0` — set in
  the settings file, not a shell export (exports don't reliably apply for this
  var).
- **Auth**: LM Studio ignores auth, but Claude Code requires a token to be set
  — any dummy value works via `ANTHROPIC_AUTH_TOKEN`.

## Setup

On the **server machine** (once): install LM Studio, download a model
(see `CLAUDE.md` for model notes — tool-calling support varies a lot between
GGUF chat templates, worth checking before picking one), start the server,
and enable **"Serve on Local Network"** — without it the server binds to
`localhost` only and is unreachable over the LAN. Give the machine a DHCP
reservation.

On the **dev machine**:

```bash
git clone <this repo> && cd local-llm-lab
cp .env.example .env        # fill in your server's IP/port
scripts/check-server.sh     # layered diagnostics: TCP → OpenAI endpoint → Anthropic endpoint
scripts/setup-claude-local.sh   # generates .claude/settings.local.json from .env
claude                      # new session in this dir now uses the local model
```

`check-server.sh` tells you *which* layer is broken when something fails
(machine unreachable vs. server not running vs. endpoint missing), which is
most of the debugging you'll ever do on this setup.

## Benchmarks

See [`benchmarks/README.md`](benchmarks/README.md) for the full schema and
comparability rules. Short version:

```bash
python3 benchmarks/run_bench.py --backend-version "LM Studio 0.4.18" \
    --gpu-backend vulkan --context 16384 --quant Q4_K_M
python3 benchmarks/report.py --last 5
```

Every run appends one full-configuration record to `benchmarks/results.jsonl`
(append-only), so any two setups ever tested can be diffed later.

## Security notes for a public repo

- `.env` (real IP) and `.claude/settings.local.json` (generated, contains the
  IP) are gitignored from the first commit. Only `.env.example` with
  placeholders is committed.
- Nothing here exposes the server beyond your LAN. Don't port-forward LM Studio
  to the internet; it has no auth.
