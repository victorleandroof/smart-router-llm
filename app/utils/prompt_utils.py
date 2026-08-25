import re
import logging

logger = logging.getLogger(__name__)

def _extract_message_text(msg: dict) -> str:
    content = msg.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        return " ".join(parts)
    return ""

def extract_prompt_text(data: dict) -> str:
    """
    Extrai o texto relevante para classificação de tier.
    Usa apenas a última mensagem 'user' (o pedido atual), não o histórico
    inteiro — concatenar toda a conversa dilui o pedido atual em meio a
    system prompt/tool history, e os classificadores (embedding de 256
    tokens, prompt truncado em 500 chars) só enxergam o início da string.
    """
    messages = data.get("messages", [])

    for msg in reversed(messages):
        if msg.get("role") == "user":
            text = _extract_message_text(msg)
            if text.strip():
                return text

    text_parts = [_extract_message_text(msg) for msg in messages]
    return " ".join(part for part in text_parts if part)

def sanitize_messages_preserve_system(messages: list) -> list:
    """
    Preserva o role 'system' original.
    Não converte system → user (diferente do router original).
    Preserva também tool_calls/tool_call_id/name — necessários para tool calling.
    """
    sanitized = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")

        # Remove headers problemáticos do Anthropic sem mudar o role
        if role == "system" and isinstance(content, str):
            content = _strip_problematic_headers(content)

        new_msg = {"role": role, "content": content}
        if "tool_calls" in msg:
            new_msg["tool_calls"] = msg["tool_calls"]
        if "tool_call_id" in msg:
            new_msg["tool_call_id"] = msg["tool_call_id"]
        if "name" in msg:
            new_msg["name"] = msg["name"]

        sanitized.append(new_msg)

    return sanitized

def _strip_problematic_headers(content: str) -> str:
    problematic_patterns = [
        r"(?i)anthropic-version:[^\n]*\n?",
        r"(?i)x-api-key:[^\n]*\n?",
    ]
    for pattern in problematic_patterns:
        content = re.sub(pattern, "", content)
    return content.strip()

def normalize_prompt(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text