import os
import sys
import yaml
import logging
import json
import litellm
import asyncio
import uvicorn
from litellm.proxy.proxy_server import app, initialize
from starlette.middleware.base import BaseHTTPMiddleware
from app.router.smart_router import router_instance
from app.router.qwen_custom_llm import qwen_custom_llm_instance


# Projeto na path ANTES de qualquer import de app.*
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s"
)
logger = logging.getLogger(__name__)

class StripAnthropicBeta:
    """ASGI puro — strip headers + limpeza do body JSON antes do LiteLLM."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # 1. Strip todos headers anthropic-*
        scope["headers"] = [
            (k, v)
            for k, v in scope.get("headers", [])
            if not k.lower().startswith(b"anthropic-")
        ]

        path = scope.get("path", "")
        is_anthropic_native = "/messages" in path
        if not is_anthropic_native and "/chat/completions" not in path:
            await self.app(scope, receive, send)
            return

        # 2. Lê o body cru
        body = b""
        more = True
        while more:
            msg = await receive()
            if msg["type"] == "http.request":
                body += msg.get("body", b"")
                more = msg.get("more_body", False)
            else:
                break

        if not body:
            await self.app(scope, receive, send)
            return

        # 3. Modifica o JSON
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            await self.app(scope, self._fake_receive(body, receive), send)
            return

        data = self._clean_body(data, extract_system=is_anthropic_native)

        # 3b. Bug conhecido do LiteLLM 1.61.20: streaming de /v1/messages
        # perde id/name de tool_use (ver docs/known-gotchas.md). Contorno:
        # força stream=false internamente (resposta não-streaming já tem
        # id/name corretos) e serializa como SSE Anthropic na saída —
        # ver _fake_stream_send/_build_anthropic_sse_events.
        is_fake_stream = (
            is_anthropic_native
            and data.get("stream") is True
            and bool(data.get("tools"))
        )
        if is_fake_stream:
            data["stream"] = False

        new_body = json.dumps(data).encode("utf-8")

        # 4. Atualiza content-length
        scope["headers"] = [
            (k, v) if k.lower() != b"content-length"
            else (k, str(len(new_body)).encode())
            for k, v in scope["headers"]
        ]

        send_target = self._fake_stream_send(send) if is_fake_stream else send
        await self.app(scope, self._fake_receive(new_body, receive), send_target)

    def _fake_stream_send(self, send):
        """Envolve `send` para bufferizar a resposta não-streaming completa
        e reemiti-la como SSE Anthropic válido (com tool_use id/name corretos),
        contornando o bug do LiteLLM 1.61.20 que perde essa informação quando
        a resposta é gerada em modo streaming de verdade."""
        buffered = {"start": None, "body": b""}

        async def wrapped_send(message):
            if message["type"] == "http.response.start":
                buffered["start"] = message
                return
            if message["type"] == "http.response.body":
                buffered["body"] += message.get("body", b"")
                if message.get("more_body", False):
                    return
                await self._flush_fake_stream(buffered, send)
                return
            await send(message)

        return wrapped_send

    async def _flush_fake_stream(self, buffered, send):
        start_msg = buffered["start"]
        status = start_msg["status"]
        body = buffered["body"]

        if status == 200:
            try:
                response_data = json.loads(body)
                sse_body = self._build_anthropic_sse_body(response_data)
            except Exception:
                logger.exception("[FakeStream] Falha ao converter resposta em SSE, enviando corpo original")
                sse_body = None
        else:
            sse_body = None

        if sse_body is None:
            await send(start_msg)
            await send({"type": "http.response.body", "body": body, "more_body": False})
            return

        headers = [
            (k, v) for k, v in start_msg.get("headers", [])
            if k.lower() not in (b"content-length", b"content-type")
        ]
        headers.append((b"content-type", b"text/event-stream"))
        headers.append((b"content-length", str(len(sse_body)).encode()))
        await send({"type": "http.response.start", "status": status, "headers": headers})
        await send({"type": "http.response.body", "body": sse_body, "more_body": False})

    @staticmethod
    def _sse_event(event_type, data):
        return f"event: {event_type}\ndata: {json.dumps(data)}\n\n".encode("utf-8")

    def _build_anthropic_sse_body(self, response):
        """Serializa uma resposta Anthropic não-streaming completa (com
        tool_use id/name corretos) como a sequência de eventos SSE que um
        cliente streaming espera receber."""
        events = []

        message_start = {k: v for k, v in response.items() if k != "content"}
        message_start["content"] = []
        events.append(self._sse_event(
            "message_start",
            {"type": "message_start", "message": message_start},
        ))

        content = response.get("content") or []
        for index, block in enumerate(content):
            if block.get("type") == "tool_use":
                content_block = {
                    "type": "tool_use",
                    "id": block.get("id"),
                    "name": block.get("name"),
                    "input": {},
                }
                delta = {
                    "type": "input_json_delta",
                    "partial_json": json.dumps(block.get("input", {})),
                }
            else:
                content_block = {"type": "text", "text": ""}
                delta = {"type": "text_delta", "text": block.get("text", "")}

            events.append(self._sse_event(
                "content_block_start",
                {"type": "content_block_start", "index": index, "content_block": content_block},
            ))
            events.append(self._sse_event(
                "content_block_delta",
                {"type": "content_block_delta", "index": index, "delta": delta},
            ))
            events.append(self._sse_event(
                "content_block_stop",
                {"type": "content_block_stop", "index": index},
            ))

        events.append(self._sse_event("message_delta", {
            "type": "message_delta",
            "delta": {
                "stop_reason": response.get("stop_reason"),
                "stop_sequence": response.get("stop_sequence"),
            },
            "usage": {"output_tokens": (response.get("usage") or {}).get("output_tokens", 0)},
        }))
        events.append(self._sse_event("message_stop", {"type": "message_stop"}))

        return b"".join(events)

    def _fake_receive(self, body, receive):
        """Entrega o body reconstituído uma vez; depois delega ao `receive`
        original — necessário para propagar http.disconnect em respostas
        streaming (Starlette faz polling de receive() via listen_for_disconnect
        enquanto a resposta está sendo enviada; sem isso, o loop nunca cede
        controle e trava o event loop inteiro)."""
        sent = False
        async def wrapped_receive():
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()
        return wrapped_receive

    def _clean_body(self, data, extract_system=True):
        # 1. Move system messages do array para campo top-level
        # Só faz sentido no formato Anthropic Messages API (/messages).
        # No formato OpenAI (/chat/completions) role=system deve
        # permanecer dentro do array — um campo "system" solto é
        # rejeitado pelo schema do Azure/Mistral (422 extra_forbidden).
        if extract_system:
            messages = data.get("messages", [])
            system_parts = []
            cleaned = []
            for msg in messages:
                if msg.get("role") == "system":
                    c = msg.get("content", "")
                    if isinstance(c, str):
                        system_parts.append(c)
                    elif isinstance(c, list):
                        for block in c:
                            if isinstance(block, dict) and block.get("type") == "text":
                                system_parts.append(block.get("text", ""))
                else:
                    cleaned.append(msg)

            if system_parts:
                existing = data.get("system", "")
                merged = "\n\n".join(system_parts)
                if isinstance(existing, str) and existing:
                    data["system"] = existing + "\n\n" + merged
                else:
                    data["system"] = merged

            data["messages"] = cleaned

        # 2. Remove campos Anthropic-específicos não traduzidos pelo adapter
        # experimental do LiteLLM (translatable_anthropic_params só cobre
        # messages/metadata/system/tool_choice/tools) — thinking/output_config
        # vazam crus para o schema OpenAI do Flow e causam 422 extra_forbidden.
        if extract_system:
            for key in ("thinking", "output_config"):
                data.pop(key, None)

        # 3. Remove tools internos do Claude Code
        tools = data.get("tools", [])
        if tools:
            INTERNAL_TOOLS = {
                "ExitPlanMode", "AskUserQuestion", "TodoWrite",
                "ListMcpResources", "ReadMcpResource",
            }
            ANTHROPIC_TOOL_TYPES = {
                "computer_20250124", "bash_20250124", "text_editor_20250124",
                "web_search_20250305", "code_execution_20250522",
            }
            data["tools"] = [
                t for t in tools
                if isinstance(t, dict)
                and t.get("name") not in INTERNAL_TOOLS
                and t.get("type") not in ANTHROPIC_TOOL_TYPES
            ]
            if not data["tools"]:
                data.pop("tools", None)

        return data

# 1. Middleware no nível HTTP
app.add_middleware(StripAnthropicBeta)


def get_config_path():
    return os.path.join(PROJECT_ROOT, "..", "config.yaml")

async def start_litellm():
    from litellm.utils import custom_llm_setup

    litellm.custom_provider_map.append(
        {"provider": "qwen-toolcalling", "custom_handler": qwen_custom_llm_instance}
    )
    custom_llm_setup()
    logger.info("QwenToolCallingLLM registrado como custom provider")
    litellm.callbacks = [router_instance]
    logger.info("SmartRouter v2 registrado")
    _config_path = get_config_path()
    logger.info(f"Inicializando LiteLLM com config: {_config_path}")
    result = initialize(config=_config_path)
    if asyncio.iscoroutine(result):
        await result
    else:
        logger.info("LiteLLM inicializado com sucesso.")

async def start_uvicorn():
    config = uvicorn.Config(app, host="0.0.0.0", port=4000, workers=4, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

async def main():
    await asyncio.gather(
        start_litellm(),
        start_uvicorn()
    )

if __name__ == "__main__":
    asyncio.run(main())