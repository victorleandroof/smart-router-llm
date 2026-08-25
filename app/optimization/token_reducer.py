import logging

logger = logging.getLogger(__name__)

try:
    from llmlingua import PromptCompressor
    LLMLINGUA_AVAILABLE = True
except ImportError:
    LLMLINGUA_AVAILABLE = False

try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False

class TokenReducer:
    def __init__(self):
        self._compressor = None
        if LLMLINGUA_AVAILABLE:
            try:
                import torch
                # Força CPU antes de instanciar o PromptCompressor
                torch.set_num_threads(4)

                self._compressor = PromptCompressor(
                    model_name="microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank",
                    use_llmlingua2=True,
                    # Sem parâmetro device — versão instalada não suporta
                )
                logger.info("[TokenReducer] LLMLingua inicializado (CPU forçado via torch)")
            except Exception as e:
                logger.warning(f"[TokenReducer] Falha LLMLingua: {e}")
                self._compressor = None

        self._encoding = None
        if TIKTOKEN_AVAILABLE:
            try:
                self._encoding = tiktoken.get_encoding("cl100k_base")
            except Exception:
                pass

    def compress_prompt(
        self, system_prompt: str, user_prompt: str, rate: float = 0.5
    ) -> tuple[str, str]:
        if self._compressor is None:
            return system_prompt, user_prompt

        try:
            compressed_system = self._compressor.compress_prompt(
                system_prompt,
                rate=rate,
                force_tokens=["\n", "?", ".", ","],
                drop_consecutive_newlines=True,
            )["compressed_prompt"]

            compressed_user = self._compressor.compress_prompt(
                user_prompt,
                rate=rate,
                force_tokens=["\n", "?", ".", ","],
                drop_consecutive_newlines=True,
            )["compressed_prompt"]

            return compressed_system, compressed_user

        except Exception as e:
            logger.warning(f"[TokenReducer] Erro compressão: {e}")
            return system_prompt, user_prompt

    def truncate_context(
        self, messages: list, max_context_tokens: int = 100000
    ) -> list:
        if not self._encoding:
            return messages[-20:]  # fallback simples: últimas 20 mensagens

        total_tokens = 0
        result = []

        for msg in reversed(messages):
            content = msg.get("content", "")
            if isinstance(content, str):
                msg_tokens = len(self._encoding.encode(content))
            elif isinstance(content, list):
                msg_tokens = sum(
                    len(self._encoding.encode(b.get("text", "")))
                    for b in content
                    if isinstance(b, dict) and b.get("type") == "text"
                )
            else:
                msg_tokens = 0

            if total_tokens + msg_tokens > max_context_tokens:
                break

            result.insert(0, msg)
            total_tokens += msg_tokens

        return result

    def _message_tokens(self, msg: dict) -> int:
        content = msg.get("content", "")
        if isinstance(content, str):
            return len(self._encoding.encode(content))
        if isinstance(content, list):
            return sum(
                len(self._encoding.encode(b.get("text", "")))
                for b in content
                if isinstance(b, dict) and b.get("type") == "text"
            )
        return 0

    def _find_tool_blocks(self, messages: list) -> list[tuple[int, int]]:
        """Identifica blocos protegidos: assistant(tool_calls) -> tool* -> assistant(continuação)."""
        blocks = []
        i = 0
        n = len(messages)

        while i < n:
            if messages[i].get("role") == "assistant" and messages[i].get("tool_calls"):
                start = i
                j = i + 1
                while j < n and messages[j].get("role") == "tool":
                    j += 1
                end = j
                if j < n and messages[j].get("role") == "assistant":
                    end = j + 1
                blocks.append((start, end))
                i = end
            else:
                i += 1

        return blocks

    def truncate_preserving_tool_blocks(
        self, messages: list, max_context_tokens: int = 4000
    ) -> list:
        if not messages:
            return messages

        if not self._encoding:
            return messages[-20:] or messages[-1:]

        total_tokens = sum(self._message_tokens(m) for m in messages)
        if total_tokens <= max_context_tokens:
            return messages

        blocks = self._find_tool_blocks(messages)
        protected_indices = set()
        for start, end in blocks:
            protected_indices.update(range(start, end))

        # Nunca remove a última mensagem (turno atual) — evita esvaziar a
        # conversa e provocar "Conversation must have at least one message".
        last_idx = len(messages) - 1
        protected_indices.add(last_idx)

        removed_count = 0
        kept = list(messages)
        kept_indices = list(range(len(messages)))

        idx_pos = 0
        while total_tokens > max_context_tokens and idx_pos < len(kept_indices):
            orig_idx = kept_indices[idx_pos]
            if orig_idx in protected_indices:
                idx_pos += 1
                continue
            total_tokens -= self._message_tokens(messages[orig_idx])
            kept_indices.pop(idx_pos)
            removed_count += 1

        if total_tokens > max_context_tokens and blocks:
            for start, end in blocks:
                if total_tokens <= max_context_tokens:
                    break
                if last_idx in range(start, end):
                    continue
                block_indices = set(range(start, end))
                block_tokens = sum(
                    self._message_tokens(messages[i])
                    for i in kept_indices
                    if i in block_indices
                )
                kept_indices = [i for i in kept_indices if i not in block_indices]
                total_tokens -= block_tokens
                removed_count += (end - start)

        result = [messages[i] for i in kept_indices]

        if removed_count:
            logger.info(
                f"[TokenReducer] Truncamento preservando blocos de tool: "
                f"{removed_count} mensagem(ns) removida(s), {total_tokens} tokens restantes"
            )

        return result