"""NoteForge 日志模块 — 基于标准库 logging 的轻量封装。

使用方式：
    from noteforge.logging import get_logger
    log = get_logger(__name__)
    log.info("消息")
    log.warning("警告")
    log.error("错误")

环境变量 LOG_LEVEL 控制日志级别（DEBUG/INFO/WARNING/ERROR），默认 INFO。
"""

import logging
import os
import sys


def get_logger(name: str) -> logging.Logger:
    """获取已配置的 logger 实例。"""
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        fmt = logging.Formatter(
            "[%(asctime)s] [%(levelname)-7s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(fmt)
        logger.addHandler(handler)

        level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
        level = getattr(logging, level_name, logging.INFO)
        logger.setLevel(level)

    return logger
