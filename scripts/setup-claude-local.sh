#!/usr/bin/env bash
# Generate .claude/settings.local.json (gitignored) so Claude Code sessions
# launched INSIDE THIS REPO use the local LM Studio server instead of the
# Anthropic API. Other projects are unaffected.
#
# Why settings.local.json instead of shell exports:
#  - scoped to this project only, and it's gitignored (LAN IP never committed)
#  - CLAUDE_CODE_ATTRIBUTION_HEADER is reported to not apply reliably via
#    shell export; the settings-file env block is the documented-safe path.
set -euo pipefail

cd "$(dirname "$0")/.."
[ -f .env ] || { echo "Copy .env.example to .env and fill it in first."; exit 1; }
source .env

MODEL="${LLM_MODEL:-}"
if [ -z "$MODEL" ]; then
  MODEL=$(curl -sS -m 10 "http://$LLM_HOST:$LLM_PORT/v1/models" \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["data"][0]["id"])')
  echo "Auto-detected model: $MODEL"
fi

mkdir -p .claude
cat > .claude/settings.local.json <<EOF
{
  "env": {
    "ANTHROPIC_BASE_URL": "http://$LLM_HOST:$LLM_PORT",
    "ANTHROPIC_AUTH_TOKEN": "${LLM_AUTH_TOKEN:-lmstudio}",
    "ANTHROPIC_MODEL": "$MODEL",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "$MODEL",
    "CLAUDE_CODE_ATTRIBUTION_HEADER": "0"
  }
}
EOF
echo "Wrote .claude/settings.local.json -> http://$LLM_HOST:$LLM_PORT ($MODEL)"
echo "Start a new 'claude' session inside this directory to use the local model."
