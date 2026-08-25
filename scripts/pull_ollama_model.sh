#!/bin/bash
set -e

MODEL="${OLLAMA_MODEL:-qwen2.5:1.5b}"
LOCAL_TIER_MODEL="${OLLAMA_LOCAL_TIER_MODEL:-qwen2.5:7b-instruct}"

echo "Pulling $MODEL..."
ollama pull "$MODEL"

echo "Pulling $LOCAL_TIER_MODEL (tier 'local' — tool calling habilitado)..."
ollama pull "$LOCAL_TIER_MODEL"

echo "Creating custom model from Modelfile..."
if [ -f /root/Modelfile ]; then
    ollama create smart-router -f /root/Modelfile 2>/dev/null || true
fi

echo "Ollama models ready."
ollama list