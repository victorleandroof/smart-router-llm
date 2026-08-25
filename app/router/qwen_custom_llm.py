import json
import logging
import uuid

import aiohttp
import litellm
from litellm.llms.custom_llm import CustomLLM, CustomLLMError
from litellm.types.utils import GenericStreamingChunk

from app.utils.tool_filter import filter_tools_for_qwen, inject_cwd_guidance

logger = logging.getLogger(__name__)


OLLAMA_NUM_CTX = 16384


def _build_ollama_request(model: str, messages: list, optional_params: dict) -> dict:
    """Monta o payload não-streaming para /api/chat, espelhando o formato
    que litellm.llms.ollama_chat.ollama_acompletion() usa internamente."""
    options = dict(optional_params)
    tools = options.pop("tools", None)
    format_ = options.pop("format", None)
    options.pop("function_name", None)
    options.pop("functions_unsupported_model", None)
    options.setdefault("num_ctx", OLLAMA_NUM_CTX)

    data = {
        "model": model,
        "messages": messages,
        "options": options,
        "stream": False,
    }
    if tools:
        original_count = len(tools)
        tools = filter_tools_for_qwen(tools, messages)
        data["tools"] = tools
        data["messages"] = inject_cwd_guidance(messages, tools)
        logger.info(
            f"[QwenToolCallingLLM] Enviando {len(tools)}/{original_count} tools, "
            f"{len(json.dumps(tools))} chars: {[t.get('function', {}).get('name') for t in tools]}"
        )
    if format_ is not None:
        data["format"] = format_
    return data


async def _call_ollama_chat(model: str, messages: list, optional_params: dict, api_base: str) -> dict:
    url = api_base if api_base.endswith("/api/chat") else f"{api_base}/api/chat"
    data = _build_ollama_request(model=model, messages=messages, optional_params=optional_params)

    timeout = aiohttp.ClientTimeout(total=litellm.request_timeout)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        resp = await session.post(url, json=data)
        if resp.status != 200:
            text = await resp.text()
            raise CustomLLMError(status_code=resp.status, message=text)
        response_json = await resp.json()
        logger.info(f"[QwenToolCallingLLM] Ollama raw response: {json.dumps(response_json)}")
        return response_json


def _extract_tool_use(message: dict) -> dict | None:
    tool_calls = message.get("tool_calls")
    if not tool_calls:
        return None
    tool_call = tool_calls[0]
    function = tool_call.get("function", {})
    arguments = function.get("arguments", {})
    if not isinstance(arguments, str):
        arguments = json.dumps(arguments)
    return {
        "id": tool_call.get("id") or f"call_{uuid.uuid4()}",
        "type": "function",
        "function": {
            "name": function.get("name") or "",
            "arguments": arguments,
        },
        "index": 0,
    }


class QwenToolCallingLLM(CustomLLM):
    """Contorna o bug de streaming do provider `ollama_chat` (LiteLLM 1.61.20)
    que nunca extrai `tool_calls` do stream — só o caminho não-streaming
    (`ollama_acompletion`) faz isso corretamente. Aqui, `astreaming()` faz a
    chamada real não-streaming ao Ollama e devolve o resultado como um único
    GenericStreamingChunk, deixando o CustomStreamWrapper do próprio LiteLLM
    (que já trata `tool_use` de providers customizados) reconstruir o Delta."""

    async def astreaming(
        self,
        model: str,
        messages: list,
        api_base: str,
        custom_prompt_dict: dict,
        model_response,
        print_verbose,
        encoding,
        api_key,
        logging_obj,
        optional_params: dict,
        acompletion=None,
        litellm_params=None,
        logger_fn=None,
        headers=None,
        timeout=None,
        client=None,
    ):
        try:
            response_json = await _call_ollama_chat(
                model=model, messages=messages, optional_params=optional_params, api_base=api_base
            )
        except CustomLLMError:
            raise
        except Exception as e:
            logger.warning(f"[QwenToolCallingLLM] Falha ao chamar Ollama: {e}")
            raise CustomLLMError(status_code=500, message=str(e))

        message = response_json.get("message", {})
        tool_use = _extract_tool_use(message)

        prompt_tokens = response_json.get("prompt_eval_count", 0)
        completion_tokens = response_json.get("eval_count", 0)

        chunk: GenericStreamingChunk = {
            "text": message.get("content") or "",
            "tool_use": tool_use,
            "is_finished": True,
            "finish_reason": "tool_calls" if tool_use else "stop",
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
            "index": 0,
        }
        yield chunk

    async def acompletion(
        self,
        model: str,
        messages: list,
        api_base: str,
        custom_prompt_dict: dict,
        model_response,
        print_verbose,
        encoding,
        api_key,
        logging_obj,
        optional_params: dict,
        acompletion=None,
        litellm_params=None,
        logger_fn=None,
        headers=None,
        timeout=None,
        client=None,
    ):
        try:
            response_json = await _call_ollama_chat(
                model=model, messages=messages, optional_params=optional_params, api_base=api_base
            )
        except CustomLLMError:
            raise
        except Exception as e:
            logger.warning(f"[QwenToolCallingLLM] Falha ao chamar Ollama: {e}")
            raise CustomLLMError(status_code=500, message=str(e))

        message = response_json.get("message", {})
        tool_use = _extract_tool_use(message)

        if tool_use:
            model_response.choices[0].message = litellm.Message(
                content=None,
                tool_calls=[tool_use],
            )
            model_response.choices[0].finish_reason = "tool_calls"
        else:
            model_response.choices[0].message = litellm.Message(
                content=message.get("content") or ""
            )
            model_response.choices[0].finish_reason = "stop"

        model_response.model = f"qwen-toolcalling/{model}"
        prompt_tokens = response_json.get("prompt_eval_count", 0)
        completion_tokens = response_json.get("eval_count", 0)
        model_response.usage = litellm.Usage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )
        return model_response


qwen_custom_llm_instance = QwenToolCallingLLM()
