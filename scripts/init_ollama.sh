#!/bin/sh

wait_for_ollama() {
  local url="${1:-http://localhost:11434/api/tags}"
  local max_retries="${2:-30}"
  local interval="${3:-2}"

  for i in $(seq 1 "$max_retries"); do
    if curl -sf "$url" >/dev/null 2>&1; then
      echo "Ollama pronto (tentativa ${i})"
      return 0
    fi
    sleep "$interval"
  done

  echo "Erro: Ollama não respondeu em $((max_retries * interval))s" >&2
  return 1
}


nohup ollama serve > ollama.log 2>&1 &

wait_for_ollama "http://localhost:11434/api/tags" 30 2 || exit 1