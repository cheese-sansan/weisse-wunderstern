"""NoteForge JSON 解析器 — 从 LLM 输出中提取并修复 JSON。"""

import json
import re


def extract_json(text: str) -> tuple:
    """
    从 LLM 自由文本中提取 JSON 对象并解析。

    处理常见 LLM 输出问题：
    - markdown 代码块包裹 (```json ... ```)
    - 首尾的自然语言引言/结语
    - 尾逗号 (trailing commas)
    - 单引号 JSON

    返回 (parsed_dict_or_list, error_str_or_None)。
    """
    if not isinstance(text, str) or not text.strip():
        return None, "输入为空"

    original = text.strip()

    # 1. 提取 markdown 代码块中的 JSON
    code_patterns = [
        r"```(?:json)?\s*\n?(.*?)\n?```",   # ```json ... ```
        r"`{1,2}(.*?)`{1,2}",                # `...`
    ]
    for pat in code_patterns:
        m = re.search(pat, original, re.DOTALL)
        if m:
            text = m.group(1).strip()
            break

    # 2. 试图找到 JSON 对象/数组的边界
    # 找第一个 { 或 [ 和最后一个 } 或 ]
    obj_match = re.search(r"\{.*\}", text, re.DOTALL)
    arr_match = re.search(r"\[.*\]", text, re.DOTALL)

    if obj_match and (not arr_match or obj_match.start() <= arr_match.start()):
        text = obj_match.group(0)
    elif arr_match:
        text = arr_match.group(0)

    text = text.strip()

    # 3. 修复常见问题：尾逗号
    text = re.sub(r",\s*([}\]])", r"\1", text)
    # 单引号 → 双引号（仅当键/值被单引号包裹时）
    text = re.sub(r"'([^']*)'(\s*:)", r'"\1"\2', text)  # 'key':
    text = re.sub(r"(:\s*)'([^']*)'", r'\1"\2"', text)   # : 'value'

    # 4. 尝试解析
    for attempt in range(3):
        try:
            return json.loads(text), None
        except json.JSONDecodeError as e:
            if attempt == 0:
                # 尝试移除 BOM 和其他隐藏字符
                text = text.encode("utf-8").decode("utf-8-sig").strip()
            elif attempt == 1:
                # 尝试补充缺失的闭合括号
                if text.count("{") > text.count("}"):
                    text += "}" * (text.count("{") - text.count("}"))
                if text.count("[") > text.count("]"):
                    text += "]" * (text.count("[") - text.count("]"))
            else:
                return None, str(e)

    return None, "解析失败"


def safe_extract(text: str, default=None):
    """安全提取 JSON，失败时返回 default。"""
    result, error = extract_json(text)
    if error:
        return default
    return result
