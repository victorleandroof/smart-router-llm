import re
import logging
import os
import sys

# Garante que o diretório app está no path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from litellm import CustomLogger
from app.cache.router_cache import RouterCache
from app.router.semantic_router import SemanticRouter
from app.router.llm_router import LLMRouter
from app.optimization.token_reducer import TokenReducer
from app.utils.prompt_utils import extract_prompt_text, sanitize_messages_preserve_system
from app.utils.tool_sanitizer import (
    sanitize_for_provider,
    should_skip_compression,
    has_tool_history,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s"
)
logger = logging.getLogger(__name__)


class SmartRouterV2(CustomLogger):
    MODEL_TIERS = {
        "simple": "mistral-small-2503",
        "local": "qwen3.5-local",
        "standard": "gemini-2.5-flash",
        "complex": "gemini-3.1-pro",
    }
    DEFAULT_MODEL = "gemini-2.5-flash"

    FALLBACK_SIMPLE_PATTERNS = [
        r"\b(crud|boilerplate|scaffold|enum|getter|setter|dto|mapper|type|interface)\b",
    ]
    FALLBACK_LOCAL_PATTERNS = [
        r"\b(html|landing page|p[áa]gina web|formul[áa]rio html|css|template)\b",
        r"\b(script simples|small script|standalone script|fun[çc][ãa]o util(it[áa]ria)?|utility function)\b",
    ]
    FALLBACK_STANDARD_PATTERNS = [
        r"\b(documento|documenta[çc][ãa]o|especifica[çc][ãa]o|spec|prd|readme)\b",
        r"\b(document|documentation|specification|requirements doc)\b",
    ]
    FALLBACK_COMPLEX_PATTERNS = [
        r"\b(race condition|code review|CR|deadlock|memory leak|optimi[sz]e|big.?o)\b",
        r"\b(architecture|distributed.*system|consensus|security.*audit)\b",
    ]

    def __init__(self):
        self._semantic_router = SemanticRouter()
        self._llm_router = LLMRouter()
        self._token_reducer = TokenReducer()
        self._cache = RouterCache()
        self._mistral_tool_safety_net = os.environ.get(
            "MISTRAL_TOOL_SAFETY_NET", "false"
        ).lower() == "true"
        self._qwen_tool_safety_net = os.environ.get(
            "QWEN_TOOL_SAFETY_NET", "false"
        ).lower() == "true"
        self._stats = {
            "cache_hits": 0,
            "semantic_hits": 0,
            "llm_router_calls": 0,
            "regex_fallback": 0,
            "total_requests": 0,
        }

    async def async_pre_call_hook(
        self, user_api_key_dict, cache, data, call_type
    ):
        self._stats["total_requests"] += 1
        self._cache.increment_stat("total_requests")

        has_tools = bool(data.get("tools") or data.get("tool_choice"))

        prompt_text = extract_prompt_text(data)
        if not prompt_text:
            data["model"] = self.DEFAULT_MODEL
            return data

        # ── CAMADA 1: Cache de routing ──
        cached_decision = self._cache.get_routing_decision(prompt_text)
        if cached_decision:
            self._stats["cache_hits"] += 1
            self._cache.increment_stat("cache_hits")
            data["model"] = self._route_with_tool_awareness(
                data.get("messages", []), cached_decision["model"], has_tools
            )
            data = self._apply_token_reduction(data)
            return data

        # ── CAMADA 2: Semantic Router ──
        tier, confidence = self._semantic_router.route(prompt_text)

        if tier == "unknown" or confidence < 0.75:
            # ── CAMADA 3: LLM Router local ──
            tier, confidence = self._llm_router.classify(prompt_text)
            self._stats["llm_router_calls"] += 1
            self._cache.increment_stat("llm_router_calls")

            if tier == "unknown":
                # ── CAMADA 4: Regex fallback ──
                tier = self._regex_fallback(prompt_text)
                self._stats["regex_fallback"] += 1
                self._cache.increment_stat("regex_fallback")
        else:
            self._stats["semantic_hits"] += 1
            self._cache.increment_stat("semantic_hits")

        model = self.MODEL_TIERS.get(tier, self.DEFAULT_MODEL)

        self._cache.set_routing_decision(prompt_text, {
            "model": model,
            "tier": tier,
            "confidence": confidence,
        })

        model = self._route_with_tool_awareness(data.get("messages", []), model, has_tools)
        data["model"] = model
        data = self._apply_token_reduction(data)

        logger.info(
            f"[SmartRouter] tier={tier} conf={confidence:.2f} model={model}"
        )

        return data

    def _apply_token_reduction(self, data: dict) -> dict:
        messages = data.get("messages", [])

        # Preserva system role (não converte para user)
        messages = sanitize_messages_preserve_system(messages)

        # TEMP DEBUG: TokenReducer desativado para isolar causa de content/tool_calls vazios do qwen-local
        # # Trunca contexto longo preservando blocos assistant(tool_calls)->tool*->assistant
        messages = self._token_reducer.truncate_preserving_tool_blocks(
            messages, max_context_tokens=400_000
        )
        # # Comprime prompts longos (skip se houver tool calls no histórico — Bug C agravante)
        if not should_skip_compression(messages):
            for msg in messages:
                content = msg.get("content", "")
                if isinstance(content, str) and len(content) > 500:
                    role = msg.get("role", "user")
                    if role == "system":
                        compressed, _ = self._token_reducer.compress_prompt(content, "", rate=0.9)
                        msg["content"] = compressed

        # Sanitização final para o provider alvo (Bugs A, B, D)
        messages = sanitize_for_provider(messages, data.get("model", ""))

        data["messages"] = messages

        if "max_tokens" not in data:
            data["max_tokens"] = 2048

        return data

    def _route_with_tool_awareness(self, messages: list, base_model: str, has_tools: bool = False) -> str:
        """Desvia de Mistral quando a requisição envolve tool calling.

        Confirmado via teste direto contra o gateway remoto (payload mínimo,
        tool_choice="auto", sem histórico): mistral-small-2503 nunca retorna
        tool_calls, sempre responde com texto narrativo — não é um problema de
        complexidade do prompt nem do pipeline de compressão/truncamento local.
        Por isso o desvio é incondicional para tools na requisição atual, e
        segue independente do circuit breaker MISTRAL_TOOL_SAFETY_NET (que
        cobre apenas o caso adicional de histórico de tool_calls em turnos de
        continuação sem tools no request atual).

        qwen2.5 (via Ollama) suporta tool_calls nativamente (confirmado com
        qwen2.5:1.5b — retorna tool_calls válido em teste direto). Como
        Claude Code sempre envia `tools` no request, esse desvio dispara em
        praticamente toda chamada tier "simple" — se o alvo fosse
        gemini-2.5-flash (pago), a economia do tier "local" nunca se
        aplicaria a essas chamadas. Por isso o desvio vai para o qwen2.5
        local (gratuito) por padrão, e só cai para gemini-2.5-flash quando
        QWEN_TOOL_SAFETY_NET está ativo (circuit breaker caso o 7b se mostre
        inconsistente em produção).
        """
        needs_tool_reroute = "mistral" in base_model.lower() and (
            has_tools or (self._mistral_tool_safety_net and has_tool_history(messages))
        )

        if needs_tool_reroute:
            if self._qwen_tool_safety_net:
                logger.info(
                    f"[SmartRouter] Rerouted from {base_model} to anthropic.claude-4-5-haiku "
                    f"(tool calling não suportado pelo Mistral; QWEN_TOOL_SAFETY_NET ativo, evitando qwen local)"
                )
                return "anthropic.claude-4-5-haiku"

            logger.info(
                f"[SmartRouter] Rerouted from {base_model} to qwen3.5-local "
                f"(tool calling não suportado pelo Mistral; qwen2.5 local suporta tool_calls nativamente, sem custo)"
            )
            return "qwen3.5-local"

        if base_model == "qwen3.5-local" and self._qwen_tool_safety_net and (
            has_tools or has_tool_history(messages)
        ):
            logger.info(
                f"[SmartRouter] Rerouted from {base_model} to anthropic.claude-4-5-haiku "
                f"(QWEN_TOOL_SAFETY_NET ativo)"
            )
            return "anthropic.claude-4-5-haiku"

        return base_model

    def _regex_fallback(self, prompt: str) -> str:
        prompt_lower = prompt.lower()
        for pattern in self.FALLBACK_COMPLEX_PATTERNS:
            if re.search(pattern, prompt_lower):
                return "complex"
        for pattern in self.FALLBACK_STANDARD_PATTERNS:
            if re.search(pattern, prompt_lower):
                return "standard"
        for pattern in self.FALLBACK_LOCAL_PATTERNS:
            if re.search(pattern, prompt_lower):
                return "local"
        for pattern in self.FALLBACK_SIMPLE_PATTERNS:
            if re.search(pattern, prompt_lower):
                return "simple"
        word_count = len(prompt_lower.split())
        if word_count < 15:
            return "simple"
        if word_count > 80:
            return "complex"
        return "standard"

    async def async_log_success_event(
        self, kwargs, response_obj, start_time, end_time
    ):
        elapsed = round((end_time - start_time).total_seconds(), 3)
        model = kwargs.get("model", "?")

        usage = getattr(response_obj, "usage", None)
        if usage:
            pt = getattr(usage, "prompt_tokens", 0)
            ct = getattr(usage, "completion_tokens", 0)
            logger.info(
                f"[SmartRouter] ✅ {elapsed}s | {model} | in:{pt} out:{ct} tokens"
            )
        else:
            logger.info(f"[SmartRouter] ✅ {elapsed}s | {model}")

    async def async_log_failure_event(
        self, kwargs, response_obj, start_time, end_time
    ):
        elapsed = round((end_time - start_time).total_seconds(), 3)
        logger.error(
            f"[SmartRouter] ❌ {elapsed}s | {kwargs.get('model', '?')} | "
            f"{type(response_obj).__name__}: {response_obj}"
        )

    def get_stats(self) -> dict:
        return {
            **self._stats,
            "cache_hit_rate": (
                self._stats["cache_hits"]
                / max(self._stats["total_requests"], 1)
            ),
        }

router_instance = SmartRouterV2()