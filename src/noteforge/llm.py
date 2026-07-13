"""
NoteForge 零依赖 LLM 客户端模块

使用 Python 标准库中的 urllib.request 向 OpenAI 兼容的 API（如 DeepSeek）发起 HTTP 请求。
"""

import json
import os
import urllib.error
import urllib.request

from noteforge.logging import get_logger

log = get_logger(__name__)

DEFAULT_API_BASE = "https://api.deepseek.com/v1"
DEFAULT_MODEL = "deepseek-chat"


def chat(prompt: str, system_prompt: str | None = None, temperature: float = 0.7) -> str | None:
    """向 LLM 接口发送对话请求。未配置 API Key 时返回 None。"""
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None

    api_base = os.environ.get("OPENAI_API_BASE", DEFAULT_API_BASE).strip()
    model = os.environ.get("LLM_MODEL", DEFAULT_MODEL).strip()

    url = api_base
    if not url.endswith("/chat/completions"):
        url = url.rstrip("/") + "/chat/completions"

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    data = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    req_data = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=req_data, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            res_body = response.read().decode("utf-8")
            res_json = json.loads(res_body)
            return res_json["choices"][0]["message"]["content"].strip()
    except urllib.error.HTTPError as e:
        log.warning("LLM 请求失败 (HTTPError %s): %s", e.code, e.reason)
    except Exception as e:
        log.warning("LLM 请求时发生异常: %s", e)

    return None
