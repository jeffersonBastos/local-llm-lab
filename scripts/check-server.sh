#!/usr/bin/env bash
# Diagnose connectivity to the LM Studio server, layer by layer.
# Usage: scripts/check-server.sh   (reads .env in repo root)
set -uo pipefail

cd "$(dirname "$0")/.."
[ -f .env ] && source .env
HOST="${LLM_HOST:?Set LLM_HOST in .env (copy .env.example)}"
PORT="${LLM_PORT:-1234}"

echo "== 1. TCP reachability =="
if nc -z -G 3 "$HOST" "$PORT" 2>/dev/null; then
  echo "OK: $HOST:$PORT accepts connections"
else
  echo "FAIL: $HOST:$PORT not reachable."
  if nc -z -G 3 "$HOST" 22 2>/dev/null; then
    echo "  Host is up (SSH port answers) -> LM Studio server is stopped, or"
    echo "  'Serve on Local Network' is off (bound to localhost), or firewall blocks $PORT."
  else
    echo "  Host entirely unreachable -> wrong IP, machine off, or network profile"
    echo "  reverted to 'Public' (blocks firewall rules). Check DHCP reservation."
  fi
  exit 1
fi

echo
echo "== 2. OpenAI-compat endpoint (/v1/models) =="
MODELS_JSON=$(curl -sS -m 10 "http://$HOST:$PORT/v1/models" 2>&1)
if echo "$MODELS_JSON" | grep -q '"data"'; then
  echo "OK. Loaded/available models:"
  echo "$MODELS_JSON" | python3 -c 'import json,sys; [print("  -", m["id"]) for m in json.load(sys.stdin)["data"]]'
else
  echo "FAIL: $MODELS_JSON"
fi

echo
echo "== 3. Anthropic-compat endpoint (/v1/messages) =="
MODEL="${LLM_MODEL:-$(echo "$MODELS_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin)["data"][0]["id"])' 2>/dev/null)}"
RESP=$(curl -sS -m 60 "http://$HOST:$PORT/v1/messages" \
  -H 'content-type: application/json' -H "x-api-key: ${LLM_AUTH_TOKEN:-lmstudio}" \
  -H 'anthropic-version: 2023-06-01' \
  -d "{\"model\":\"$MODEL\",\"max_tokens\":32,\"messages\":[{\"role\":\"user\",\"content\":\"Reply with exactly: pong\"}]}")
if echo "$RESP" | grep -q '"content"'; then
  echo "OK: model '$MODEL' responded:"
  echo "$RESP" | python3 -c 'import json,sys; print(" ", json.load(sys.stdin)["content"][0]["text"][:200])'
  echo
  echo "All checks passed. Run scripts/setup-claude-local.sh to point Claude Code here."
else
  echo "FAIL (Anthropic-compat endpoint may need LM Studio >= 0.4.1): $RESP"
  exit 1
fi
