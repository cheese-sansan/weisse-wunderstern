"""统一错误类型 — 便于调用方精确捕获和处理。"""


class LiteAgentError(Exception):
    """所有 Lite Agent Orchestrator 异常的基类。"""


class DocumentParseError(LiteAgentError):
    """文档解析失败：文件不存在、格式不支持、依赖缺失。"""


class LLMResponseError(LiteAgentError):
    """LLM 响应异常：API 请求失败、返回格式错误、JSON 解析失败。"""


class PipelineStateError(LiteAgentError):
    """管道状态异常：job 不存在、状态冲突、状态文件损坏。"""
