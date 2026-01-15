"""
日志模块

解决什么问题:
1. 提供统一的日志记录接口，避免各模块使用不同的日志方式
2. 支持日志级别、格式、输出路径的统一配置
3. 支持请求追踪，便于问题排查和系统监控

为什么现在需要:
- 日志是生产环境问题排查的关键手段
- 需要结构化日志便于后续分析和监控
- request_id 追踪是分布式系统的基础能力
"""

import sys
from loguru import logger
from typing import Optional
from pathlib import Path
import uuid
from contextvars import ContextVar

# 用于存储当前请求 ID 的上下文变量
REQUEST_ID_VAR: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


def setup_logger(log_dir: str = "./logs", log_level: str = "INFO"):
    """
    配置日志系统

    Args:
        log_dir: 日志文件目录
        log_level: 日志级别
    """
    # 创建日志目录
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    # 移除默认的处理器
    logger.remove()

    # 添加控制台输出处理器
    logger.add(
        sys.stdout,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{extra[request_id]}</cyan> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True
    )

    # 添加文件输出处理器（所有日志）
    logger.add(
        f"{log_dir}/app.log",
        level=log_level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {extra[request_id]} | {name}:{function}:{line} - {message}",
        rotation="500 MB",
        retention="30 days",
        encoding="utf-8"
    )

    # 添加文件输出处理器（仅错误日志）
    logger.add(
        f"{log_dir}/error.log",
        level="ERROR",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {extra[request_id]} | {name}:{function}:{line} - {message}",
        rotation="100 MB",
        retention="30 days",
        encoding="utf-8"
    )


def get_logger(name: Optional[str] = None):
    """
    获取 logger 实例

    Args:
        name: logger 名称，通常使用 __name__

    Returns:
        logger 实例，带有 request_id 绑定
    """
    if name:
        return logger.bind(request_id=get_request_id()).bind(name=name)
    return logger.bind(request_id=get_request_id())


def set_request_id(request_id: Optional[str] = None):
    """
    设置当前请求 ID

    Args:
        request_id: 请求 ID，如果为 None 则自动生成
    """
    if request_id is None:
        request_id = str(uuid.uuid4())
    REQUEST_ID_VAR.set(request_id)


def get_request_id() -> str:
    """
    获取当前请求 ID

    Returns:
        当前请求 ID，如果没有则返回 "N/A"
    """
    return REQUEST_ID_VAR.get() or "N/A"


def log_function_call(func):
    """函数调用日志装饰器"""
    def wrapper(*args, **kwargs):
        logger = get_logger(func.__module__)
        logger.info(f"开始执行函数: {func.__name__}")
        try:
            result = func(*args, **kwargs)
            logger.info(f"函数执行成功: {func.__name__}")
            return result
        except Exception as e:
            logger.error(f"函数执行失败: {func.__name__}, 错误: {e}")
            raise
    return wrapper
