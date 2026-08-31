#!/bin/bash
# Requer variável de ambiente LLM_GATEWAY_TEST_TOKEN com um Bearer token válido do gateway.
# Uso: LLM_GATEWAY_TEST_TOKEN="eyJ..." LLM_GATEWAY_BASE_URL="https://..." bash scripts/teste.sh

if [ -z "$LLM_GATEWAY_TEST_TOKEN" ]; then
  echo "Erro: defina LLM_GATEWAY_TEST_TOKEN antes de rodar este script." >&2
  exit 1
fi

if [ -z "$LLM_GATEWAY_BASE_URL" ]; then
  echo "Erro: defina LLM_GATEWAY_BASE_URL antes de rodar este script." >&2
  exit 1
fi

TENANT_HEADER="${LLM_GATEWAY_TENANT_HEADER:-X-Gateway-Tenant}"
AGENT_HEADER="${LLM_GATEWAY_AGENT_HEADER:-X-Gateway-Agent}"
TENANT="${LLM_GATEWAY_TENANT:-default}"
AGENT="${LLM_GATEWAY_AGENT:-teste}"

curl  -X POST "${LLM_GATEWAY_BASE_URL}/chat/completions" \
  -H "Authorization: Bearer ${LLM_GATEWAY_TEST_TOKEN}" \
  -H "Content-Type: application/json" \
  -H "${TENANT_HEADER}: ${TENANT}" \
  -H "${AGENT_HEADER}: ${AGENT}" \
 -d '{
    "model": "mistral-small-2503",
    "messages": [
      {"role": "user", "content": "List files in current directory"},
      {"role": "assistant", "content": null, "tool_calls": [{"id": "AbCdEf123", "type": "function", "function": {"name": "shell", "arguments": "{\"command\":\"ls\"}"}}]},
      {"role": "tool", "tool_call_id": "AbCdEf123", "content": "file1.py\nfile2.py"},
      {"role": "assistant", "content": "I found two files: file1.py and file2.py. What would you like to do next?"},
      {"role": "user", "content": "Now show file1.py"}
    ],
    "tools": [{"type": "function", "function": {"name": "shell", "description": "Run shell command", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}}}}]
  }'



curl -X POST "${LLM_GATEWAY_BASE_URL}/chat/completions"  \
  -H "Authorization: Bearer ${LLM_GATEWAY_TEST_TOKEN}" \
  -H "Content-Type: application/json" \
  -H "${TENANT_HEADER}: ${TENANT}" \
  -H "${AGENT_HEADER}: ${AGENT}" \
  -d '{
    "model": "gemini-3.1-flash-lite",
    "messages": [
      {"role": "user", "content": "List files"},
      {"role": "assistant", "content": null, "tool_calls": [{"id": "AbCdEf123", "type": "function", "function": {"name": "shell", "arguments": "{\"command\":\"ls\"}"}}]},
      {"role": "tool", "tool_call_id": "AbCdEf123", "content": "file1.py"},
      {"role": "user", "content": "Show file1.py"}
    ],
    "tools": [{"type": "function", "function": {"name": "shell", "description": "Run shell", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}}}}]
  }'
