# Graph Report - saude-orquestrator-llm  (2026-08-18)

## Corpus Check
- 24 files · ~6,211 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 146 nodes · 200 edges · 25 communities (15 shown, 10 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 13 edges (avg confidence: 0.8)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `732f78f4`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- smart_router.py
- RouterCache
- main.py
- StripAnthropicBeta
- TokenReducer
- tool_sanitizer.py
- model_name: anthropic.claude-4-5-haiku (shared fallback)
- graphify.js
- init_ollama.sh
- litellm_settings.callbacks wiring
- fastapi==0.115.6
- torch==2.13.0
- init_redis.sh
- pull_ollama_model.sh
- teste.sh
- valida_modelos.sh
- general_settings (master_key, port)
- opencode.json
- qwen_custom_llm.py
- SmartRouterV2

## God Nodes (most connected - your core abstractions)
1. `RouterCache` - 14 edges
2. `SmartRouterV2` - 14 edges
3. `TokenReducer` - 12 edges
4. `StripAnthropicBeta` - 10 edges
5. `sanitize_for_provider()` - 10 edges
6. `SemanticRouter` - 8 edges
7. `LLMRouter` - 7 edges
8. `filter_tools_for_qwen()` - 6 edges
9. `_build_ollama_request()` - 5 edges
10. `QwenToolCallingLLM` - 5 edges

## Surprising Connections (you probably didn't know these)
- `redis==8.1.0` --conceptually_related_to--> `RouterCache`  [INFERRED]
  requirements.txt → app/cache/router_cache.py
- `llmlingua==0.2.2` --conceptually_related_to--> `TokenReducer`  [INFERRED]
  requirements.txt → app/optimization/token_reducer.py
- `tiktoken==0.13.0` --conceptually_related_to--> `TokenReducer`  [INFERRED]
  requirements.txt → app/optimization/token_reducer.py
- `ollama==0.6.2` --conceptually_related_to--> `LLMRouter`  [INFERRED]
  requirements.txt → app/router/llm_router.py
- `faiss-cpu==1.15.0` --conceptually_related_to--> `SemanticRouter`  [INFERRED]
  requirements.txt → app/router/semantic_router.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **All primary-tier models fall back to anthropic.claude-4-5-haiku** — config_yaml_mistral_small_2503, config_yaml_gemini_2_5_flash, config_yaml_gemini_3_1_pro, config_yaml_anthropic_claude_4_5_haiku [EXTRACTED 1.00]
- **sentence-transformers + faiss-cpu implement the SemanticRouter embedding/similarity layer** — requirements_txt_sentence_transformers, requirements_txt_faiss_cpu, app_router_semantic_router_semanticrouter [INFERRED 0.85]
- **llmlingua + tiktoken implement TokenReducer's compress/truncate pipeline** — requirements_txt_llmlingua, requirements_txt_tiktoken, app_optimization_token_reducer_tokenreducer [INFERRED 0.85]

## Communities (25 total, 10 thin omitted)

### Community 0 - "smart_router.py"
Cohesion: 0.11
Nodes (13): LLMRouter, SemanticRouter, _extract_message_text(), extract_prompt_text(), Extrai o texto relevante para classificação de tier. Usa apenas a última…, Preserva o role 'system' original. Não converte system → user (diferente do…, sanitize_messages_preserve_system(), _strip_problematic_headers() (+5 more)

### Community 1 - "RouterCache"
Cohesion: 0.31
Nodes (3): RouterCache, Redis, redis==8.1.0

### Community 2 - "main.py"
Cohesion: 0.70
Nodes (4): get_config_path(), main(), start_litellm(), start_uvicorn()

### Community 3 - "StripAnthropicBeta"
Cohesion: 0.22
Nodes (5): Serializa uma resposta Anthropic não-streaming completa (com tool_use id/name…, Entrega o body reconstituído uma vez; depois delega ao `receive` original —…, ASGI puro — strip headers + limpeza do body JSON antes do LiteLLM., Envolve `send` para bufferizar a resposta não-streaming completa e reemiti-la…, StripAnthropicBeta

### Community 4 - "TokenReducer"
Cohesion: 0.22
Nodes (4): Identifica blocos protegidos: assistant(tool_calls) -> tool* ->…, TokenReducer, llmlingua==0.2.2, tiktoken==0.13.0

### Community 5 - "tool_sanitizer.py"
Cohesion: 0.18
Nodes (16): _block_to_text(), fix_message_ordering(), _flatten_content(), _generate_valid_id(), _is_mistral_model(), _is_ollama_model(), normalize_assistant_content(), normalize_content_for_ollama() (+8 more)

### Community 6 - "model_name: anthropic.claude-4-5-haiku (shared fallback)"
Cohesion: 0.60
Nodes (5): model_name: anthropic.claude-4-5-haiku (shared fallback), model_name: gemini-2.5-flash (tier standard), model_name: gemini-3.1-pro (tier complex), model_name: mistral-small-2503 (tier simple), router_settings.fallbacks table

### Community 22 - "opencode.json"
Cohesion: 0.50
Nodes (3): plugin, $schema, .opencode/plugins/graphify.js

### Community 24 - "qwen_custom_llm.py"
Cohesion: 0.19
Nodes (14): _build_ollama_request(), _call_ollama_chat(), _extract_tool_use(), QwenToolCallingLLM, Monta o payload não-streaming para /api/chat, espelhando o formato que…, Contorna o bug de streaming do provider `ollama_chat` (LiteLLM 1.61.20) que…, filter_tools_for_qwen(), inject_cwd_guidance() (+6 more)

### Community 25 - "SmartRouterV2"
Cohesion: 0.24
Nodes (4): Desvia de Mistral quando a requisição envolve tool calling. Confirmado via…, SmartRouterV2, has_tool_history(), CustomLogger

## Knowledge Gaps
- **19 isolated node(s):** `$schema`, `.opencode/plugins/graphify.js`, `init_redis.sh script`, `pull_ollama_model.sh script`, `teste.sh script` (+14 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **10 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `StripAnthropicBeta` connect `StripAnthropicBeta` to `main.py`?**
  _High betweenness centrality (0.117) - this node is a cross-community bridge._
- **Why does `RouterCache` connect `RouterCache` to `smart_router.py`, `SmartRouterV2`?**
  _High betweenness centrality (0.100) - this node is a cross-community bridge._
- **Why does `TokenReducer` connect `TokenReducer` to `smart_router.py`, `SmartRouterV2`?**
  _High betweenness centrality (0.092) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `RouterCache` (e.g. with `SmartRouterV2` and `redis==8.1.0`) actually correct?**
  _`RouterCache` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `SmartRouterV2` (e.g. with `RouterCache` and `TokenReducer`) actually correct?**
  _`SmartRouterV2` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `TokenReducer` (e.g. with `SmartRouterV2` and `llmlingua==0.2.2`) actually correct?**
  _`TokenReducer` has 3 INFERRED edges - model-reasoned connections that need verification._
- **What connects `$schema`, `.opencode/plugins/graphify.js`, `init_redis.sh script` to the rest of the system?**
  _19 weakly-connected nodes found - possible documentation gaps or missing edges._