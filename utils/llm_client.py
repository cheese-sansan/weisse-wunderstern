"""
零依赖 LLM 客户端模块

使用 Python 标准库中的 urllib.request 向 OpenAI 兼容的 API（如 DeepSeek）发起 HTTP 请求。
"""

import os
import json
import urllib.request
import urllib.error

DEFAULT_API_BASE = "https://api.deepseek.com/v1"
DEFAULT_MODEL = "deepseek-chat"


def chat(prompt: str, system_prompt: str = None, temperature: float = 0.7) -> str | None:
  """
  向大语言模型接口发送对话请求。

  读取系统环境变量中的以下配置：
  - OPENAI_API_KEY: API 密钥（必须，未配置时直接返回 None）
  - OPENAI_API_BASE: API 基础地址（默认为 DeepSeek 官方地址）
  - LLM_MODEL: 使用的模型名称（默认为 deepseek-chat）

  参数:
    prompt: 用户提示词
    system_prompt: 可选的系统提示词
    temperature: 温度参数，默认 0.7

  返回:
    str | None: 模型生成的文本内容，如果请求失败或未配置 Key 则返回 None
  """
  api_key = os.environ.get("OPENAI_API_KEY", "").strip()
  if not api_key:
    # 未配置 API KEY 时直接返回 None，自动切入 Mock 兜底模式
    return None

  api_base = os.environ.get("OPENAI_API_BASE", DEFAULT_API_BASE).strip()
  model = os.environ.get("LLM_MODEL", DEFAULT_MODEL).strip()

  # 规范化 API 地址，确保以 /chat/completions 结尾
  url = api_base
  if not url.endswith("/chat/completions"):
    url = url.rstrip("/") + "/chat/completions"

  # 构建 OpenAI 兼容的 messages 格式
  messages = []
  if system_prompt:
    messages.append({"role": "system", "content": system_prompt})
  messages.append({"role": "user", "content": prompt})

  data = {
    "model": model,
    "messages": messages,
    "temperature": temperature
  }

  # 请求头
  headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {api_key}"
  }

  req_data = json.dumps(data).encode("utf-8")
  req = urllib.request.Request(url, data=req_data, headers=headers, method="POST")

  try:
    # 超时时间设为 60 秒
    with urllib.request.urlopen(req, timeout=60) as response:
      res_body = response.read().decode("utf-8")
      res_json = json.loads(res_body)
      # 提取 OpenAI 兼容返回字段
      return res_json["choices"][0]["message"]["content"].strip()
  except urllib.error.HTTPError as e:
    err_msg = ""
    try:
      err_msg = e.read().decode("utf-8")
    except Exception:
      pass
    print(f"[WARN] LLM 请求失败 (HTTPError {e.code}): {e.reason}。细节: {err_msg}")
  except Exception as e:
    print(f"[WARN] LLM 请求时发生异常: {e}")

  return None
