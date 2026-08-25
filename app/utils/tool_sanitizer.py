import re
import logging
import secrets
import string

logger = logging.getLogger(__name__)

VALID_TOOL_CALL_ID = re.compile(r"^[a-zA-Z0-9]{9}$")
_ID_ALPHABET = string.ascii_letters + string.digits


def _is_mistral_model(model: str) -> bool:
    model = (model or "").lower()
    return "mistral" in model or "devstral" in model


def _is_ollama_model(model: str) -> bool:
    model = (model or "").lower()
    return "qwen" in model or "ollama" in model


def _block_to_text(block: dict) -> str:
    """Converte um content block Anthropic-native para texto simples.
    Extrai o conteúdo real de tool_use/tool_result em vez de descartá-lo —
    _flatten_content() só mantinha blocos type=='text', apagando
    silenciosamente o resultado real de uma tool (ex: saída de um `pwd`)."""
    block_type = block.get("type")
    if block_type == "text":
        return block.get("text", "")
    if block_type == "tool_use":
        return f"[tool_use {block.get('name', '')}: {block.get('input', {})}]"
    if block_type == "tool_result":
        result_content = block.get("content", "")
        if isinstance(result_content, list):
            result_content = " ".join(
                b.get("text", "") for b in result_content if isinstance(b, dict)
            )
        return f"[tool_result: {result_content}]"
    return ""


def _flatten_content(content):
    """Ollama (ollama_chat) exige content como string — rejeita listas de
    content blocks (formato usado por Claude Code) com
    'cannot unmarshal array into Go struct field ChatRequest.messages.content
    of type string'. Mistral/Gemini via Flow (OpenAI-compatible) aceitam a
    lista normalmente, então essa normalização só é aplicada para modelos
    Ollama."""
    if isinstance(content, list):
        parts = [
            _block_to_text(block)
            for block in content
            if isinstance(block, dict)
        ]
        return " ".join(p for p in parts if p)
    return content


def normalize_content_for_ollama(messages: list) -> list:
    for msg in messages:
        msg["content"] = _flatten_content(msg.get("content", ""))
    return messages


def _generate_valid_id() -> str:
    return "".join(secrets.choice(_ID_ALPHABET) for _ in range(9))


def normalize_tool_call_ids(messages: list) -> list:
    """Bug A: Mistral exige tool_call_id com exatamente 9 chars alfanuméricos."""
    id_map = {}
    normalized_count = 0

    for msg in messages:
        if msg.get("role") != "assistant":
            continue
        tool_calls = msg.get("tool_calls")
        if not tool_calls:
            continue
        for tool_call in tool_calls:
            old_id = tool_call.get("id", "")
            if not VALID_TOOL_CALL_ID.match(old_id):
                new_id = _generate_valid_id()
                id_map[old_id] = new_id
                tool_call["id"] = new_id
                normalized_count += 1

    if id_map:
        for msg in messages:
            if msg.get("role") == "tool":
                old_id = msg.get("tool_call_id")
                if old_id in id_map:
                    msg["tool_call_id"] = id_map[old_id]

    if normalized_count:
        logger.info(f"[ToolSanitizer] {normalized_count} tool_call_id(s) normalizados para Mistral")

    return messages


def fix_message_ordering(messages: list) -> list:
    """Bug B: Mistral exige role=assistant entre tool e user."""
    result = []
    i = 0
    n = len(messages)

    while i < n:
        current = messages[i]
        result.append(current)

        if i + 1 < n:
            next_msg = messages[i + 1]
            current_role = current.get("role")
            next_role = next_msg.get("role")

            if current_role == "tool" and next_role == "user":
                result.append({"role": "assistant", "content": "[Continuing after tool execution]"})
                logger.info(f"[ToolSanitizer] Inserida assistant após índice {i} (tool→user)")
            elif current_role == "user" and next_role == "user":
                result.append({"role": "assistant", "content": "[Acknowledged]"})
                logger.info(f"[ToolSanitizer] Inserida assistant após índice {i} (user→user)")

        i += 1

    return result


def normalize_assistant_content(messages: list) -> list:
    """Bug D: content vazio em assistant com tool_calls deve ser None, não ""."""
    for msg in messages:
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            content = msg.get("content")
            if isinstance(content, str) and content.strip() == "":
                msg["content"] = None
        elif msg.get("role") == "tool":
            content = msg.get("content")
            if content == "" or content == "(no output)":
                msg["content"] = "[Tool execution completed with no output]"

    return messages


def sanitize_for_provider(messages: list, model: str) -> list:
    """Orquestra a sanitização de mensagens antes do forward ao LiteLLM remoto."""
    messages = normalize_assistant_content(messages)

    if _is_mistral_model(model):
        messages = normalize_tool_call_ids(messages)
        messages = fix_message_ordering(messages)
    elif _is_ollama_model(model):
        messages = normalize_content_for_ollama(messages)

    return messages


def should_skip_compression(messages: list) -> bool:
    """Bug C (agravante): LLMLingua pode corromper metadados de tool_calls."""
    for msg in messages:
        if msg.get("tool_calls") or msg.get("role") == "tool":
            return True
    return False


def has_tool_history(messages: list) -> bool:
    return any(msg.get("tool_calls") or msg.get("role") == "tool" for msg in messages)