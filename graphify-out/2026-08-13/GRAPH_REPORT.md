# Graph Report - saude-orquestrator-llm  (2026-08-13)

## Corpus Check
- 22 files · ~4,061 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 114 nodes · 149 edges · 24 communities (14 shown, 10 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 13 edges (avg confidence: 0.8)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `7f37e279`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- smart_router.py
- RouterCache
- SmartRouterV2
- main.py
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
- prompt_utils.py

## God Nodes (most connected - your core abstractions)
1. `RouterCache` - 14 edges
2. `SmartRouterV2` - 14 edges
3. `TokenReducer` - 12 edges
4. `SemanticRouter` - 8 edges
5. `sanitize_for_provider()` - 8 edges
6. `LLMRouter` - 7 edges
7. `StripAnthropicBeta` - 6 edges
8. `sanitize_messages_preserve_system()` - 5 edges
9. `normalize_tool_call_ids()` - 4 edges
10. `should_skip_compression()` - 4 edges

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

## Communities (24 total, 10 thin omitted)

### Community 0 - "smart_router.py"
Cohesion: 0.19
Nodes (5): LLMRouter, SemanticRouter, faiss-cpu==1.15.0, ollama==0.6.2, sentence-transformers==5.7.0

### Community 1 - "RouterCache"
Cohesion: 0.31
Nodes (3): RouterCache, Redis, redis==8.1.0

### Community 2 - "SmartRouterV2"
Cohesion: 0.22
Nodes (5): Rede de segurança opcional (P3): desvia de Mistral se histórico de tools já…, SmartRouterV2, extract_prompt_text(), has_tool_history(), CustomLogger

### Community 3 - "main.py"
Cohesion: 0.24
Nodes (7): get_config_path(), main(), ASGI puro — strip headers + limpeza do body JSON antes do LiteLLM., Entrega o body reconstituído uma vez; depois delega ao `receive` original —…, start_litellm(), start_uvicorn(), StripAnthropicBeta

### Community 4 - "TokenReducer"
Cohesion: 0.22
Nodes (4): Identifica blocos protegidos: assistant(tool_calls) -> tool* ->…, TokenReducer, llmlingua==0.2.2, tiktoken==0.13.0

### Community 5 - "tool_sanitizer.py"
Cohesion: 0.21
Nodes (12): fix_message_ordering(), _generate_valid_id(), _is_mistral_model(), normalize_assistant_content(), normalize_tool_call_ids(), Bug C (agravante): LLMLingua pode corromper metadados de tool_calls., Bug A: Mistral exige tool_call_id com exatamente 9 chars alfanuméricos., Bug B: Mistral exige role=assistant entre tool e user. (+4 more)

### Community 6 - "model_name: anthropic.claude-4-5-haiku (shared fallback)"
Cohesion: 0.60
Nodes (5): model_name: anthropic.claude-4-5-haiku (shared fallback), model_name: gemini-2.5-flash (tier standard), model_name: gemini-3.1-pro (tier complex), model_name: mistral-small-2503 (tier simple), router_settings.fallbacks table

### Community 22 - "opencode.json"
Cohesion: 0.50
Nodes (3): plugin, $schema, .opencode/plugins/graphify.js

### Community 23 - "prompt_utils.py"
Cohesion: 0.50
Nodes (3): Preserva o role 'system' original. Não converte system → user (diferente do…, sanitize_messages_preserve_system(), _strip_problematic_headers()

## Knowledge Gaps
- **19 isolated node(s):** `$schema`, `.opencode/plugins/graphify.js`, `init_redis.sh script`, `pull_ollama_model.sh script`, `teste.sh script` (+14 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **10 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `RouterCache` connect `RouterCache` to `smart_router.py`, `SmartRouterV2`?**
  _High betweenness centrality (0.113) - this node is a cross-community bridge._
- **Why does `TokenReducer` connect `TokenReducer` to `smart_router.py`, `SmartRouterV2`?**
  _High betweenness centrality (0.105) - this node is a cross-community bridge._
- **Why does `SmartRouterV2` connect `SmartRouterV2` to `smart_router.py`, `RouterCache`, `TokenReducer`, `tool_sanitizer.py`?**
  _High betweenness centrality (0.103) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `RouterCache` (e.g. with `SmartRouterV2` and `redis==8.1.0`) actually correct?**
  _`RouterCache` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `SmartRouterV2` (e.g. with `RouterCache` and `TokenReducer`) actually correct?**
  _`SmartRouterV2` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `TokenReducer` (e.g. with `SmartRouterV2` and `llmlingua==0.2.2`) actually correct?**
  _`TokenReducer` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `SemanticRouter` (e.g. with `SmartRouterV2` and `faiss-cpu==1.15.0`) actually correct?**
  _`SemanticRouter` has 3 INFERRED edges - model-reasoned connections that need verification._