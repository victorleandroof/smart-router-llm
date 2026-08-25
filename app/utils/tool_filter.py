import json
import logging
import re

logger = logging.getLogger(__name__)

# Tools de escrita/edição de arquivo cujo uso sem path absoluto explícito do
# usuário arrisca gravar em diretório errado, já que o Claude Code normalmente
# informa o cwd real via bloco "Environment" no system prompt — bloco que,
# confirmado por inspeção de logs, nunca chega até este proxy em nenhum tier.
FILE_WRITE_TOOL_NAMES = {"Write", "Edit", "NotebookEdit"}

CWD_GUIDANCE = (
    "IMPORTANTE: você não recebe automaticamente o diretório de trabalho atual "
    "do usuário (working directory). Antes de usar Write, Edit ou NotebookEdit "
    "sem um caminho absoluto explicitamente informado pelo usuário na mensagem, "
    "primeiro execute Bash com o comando 'pwd' para descobrir o diretório atual "
    "e use esse caminho como base para o arquivo. Nunca escreva em pastas como "
    "Documents, Desktop, scratchpad ou qualquer outro diretório que você não "
    "tenha confirmado via pwd ou que o usuário não tenha informado "
    "explicitamente."
)

# Tools sempre disponíveis para o qwen3.5-local, independente do que a
# requisição mencione — cobrem o uso típico do tier (HTML/CSS/templates,
# scripts utilitários independentes).
CORE_TOOL_NAMES = {
    "Bash",
    "Read",
    "Write",
    "Edit",
    "NotebookEdit",
}

# Acima disso o prompt final arrisca ultrapassar o budget que o llama-server
# reserva para o prompt (~metade de num_ctx) antes mesmo de somar o resto da
# conversa — ver docs/known-gotchas.md.
MAX_TOOLS_CHARS = 40000


def _tool_name(tool: dict) -> str:
    return tool.get("function", {}).get("name", "")


def _mentioned_tool_names(messages: list) -> set:
    """Nomes de tools referenciados no histórico: por texto (prompt cita o
    nome explicitamente) ou por uso real (tool_calls/tool results), para que
    uma tool já em uso continue disponível em turnos seguintes."""
    text_parts = []
    used_names = set()

    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            text_parts.append(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text_parts.append(block.get("text", ""))

        for tool_call in msg.get("tool_calls") or []:
            name = tool_call.get("function", {}).get("name")
            if name:
                used_names.add(name)

        if msg.get("role") == "tool" and msg.get("name"):
            used_names.add(msg["name"])

    text = "\n".join(text_parts)
    return used_names, text


def inject_cwd_guidance(messages: list, tools: list) -> list:
    """Acrescenta CWD_GUIDANCE à mensagem system quando a lista final de tools
    inclui alguma tool de escrita de arquivo — o qwen3.5-local não recebe o
    bloco Environment (cwd real) que o Claude Code normalmente envia, e sem
    isso hallucina paths como ~/Documents ou ~/scratchpad."""
    if not any(_tool_name(t) in FILE_WRITE_TOOL_NAMES for t in tools):
        return messages

    for msg in messages:
        if msg.get("role") == "system":
            content = msg.get("content", "")
            if isinstance(content, str):
                msg["content"] = f"{content}\n\n{CWD_GUIDANCE}" if content else CWD_GUIDANCE
            elif isinstance(content, list):
                content.append({"type": "text", "text": CWD_GUIDANCE})
            return messages

    return [{"role": "system", "content": CWD_GUIDANCE}] + messages


def filter_tools_for_qwen(tools: list, messages: list) -> list:
    """Reduz o volume de tools enviado ao qwen3.5-local para caber no contexto
    utilizável do modelo (llama-server trunca prompts que excedem ~metade de
    num_ctx — ver docs/known-gotchas.md). Mantém um core set sempre
    disponível e força a inclusão de qualquer tool explicitamente
    mencionada/usada no histórico, para não quebrar o uso de MCPs de
    terceiros citados no prompt."""
    if not tools:
        return tools

    used_names, text = _mentioned_tool_names(messages)

    kept = []
    for tool in tools:
        name = _tool_name(tool)
        if not name:
            continue
        if name in CORE_TOOL_NAMES or name in used_names or re.search(rf"\b{re.escape(name)}\b", text):
            kept.append(tool)

    dropped = len(tools) - len(kept)
    if dropped:
        logger.info(
            f"[ToolFilter] qwen3.5-local: mantidas {len(kept)}/{len(tools)} tools "
            f"({dropped} removidas — fora do core set e não mencionadas/usadas no histórico)"
        )

    kept_chars = len(json.dumps(kept))
    if kept_chars > MAX_TOOLS_CHARS:
        logger.warning(
            f"[ToolFilter] qwen3.5-local: tools filtradas ainda somam {kept_chars} chars "
            f"(> {MAX_TOOLS_CHARS}) — risco de truncamento pelo llama-server mesmo após o filtro"
        )

    return kept
