"""
LLM 调用模块

解决什么问题:
1. 统一 LLM 调用接口，便于替换不同模型提供商
2. 封装 API 调用细节，提供重试机制
3. 支持流式输出、Token 统计等高级特性

为什么现在需要:
- LLM 调用是 RAG 的关键环节，需要统一封装
- 避免业务代码直接调用 LLM API，降低耦合
- 统一的重试和错误处理机制
"""

from typing import Dict, List, Optional, AsyncIterator
from abc import ABC, abstractmethod
import requests
import json
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from RagFlow.core.logger import get_logger

logger = get_logger(__name__)


class LLMResponse:
    """LLM 响应"""

    def __init__(
        self,
        content: str,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
        total_tokens: Optional[int] = None
    ):
        self.content = content
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens


class LLMModel(ABC):
    """LLM 模型抽象基类"""

    @abstractmethod
    def chat(
        self,
        messages: List[Dict],
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> LLMResponse:
        """
        对话接口

        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大 token 数

        Returns:
            LLM 响应
        """
        pass


class DeepSeekLLM(LLMModel):
    """DeepSeek LLM 实现"""

    def __init__(self, api_base: str, api_key: str, model: str = "deepseek-chat"):
        """
        初始化 DeepSeek LLM

        Args:
            api_base: API 基础地址
            api_key: API 密钥
            model: 模型名称
        """
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.chat_url = f"{self.api_base}/chat/completions"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((requests.RequestException, requests.Timeout))
    )
    def chat(
        self,
        messages: List[Dict],
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> LLMResponse:
        """
        调用 DeepSeek 对话接口

        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大 token 数

        Returns:
            LLM 响应
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        try:
            response = requests.post(
                self.chat_url,
                headers=headers,
                json=payload,
                timeout=60
            )
            response.raise_for_status()

            result = response.json()

            if "choices" not in result or len(result["choices"]) == 0:
                raise ValueError(f"API 返回格式错误: {result}")

            content = result["choices"][0]["message"]["content"]

            # 提取 token 统计
            usage = result.get("usage", {})
            prompt_tokens = usage.get("prompt_tokens")
            completion_tokens = usage.get("completion_tokens")
            total_tokens = usage.get("total_tokens")

            logger.info(
                f"LLM 调用成功 - "
                f"prompt_tokens: {prompt_tokens}, "
                f"completion_tokens: {completion_tokens}, "
                f"total_tokens: {total_tokens}"
            )

            return LLMResponse(
                content=content,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens
            )

        except requests.HTTPError as e:
            logger.error(f"DeepSeek API 调用失败: {e.response.text if hasattr(e, 'response') else e}")
            raise
        except Exception as e:
            logger.error(f"DeepSeek API 调用异常: {e}")
            raise


class LLMService:
    """LLM 服务封装"""

    def __init__(self, model: LLMModel):
        """
        初始化 LLM 服务

        Args:
            model: LLM 模型实例
        """
        self.model = model

    def chat(
        self,
        messages: List[Dict],
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> LLMResponse:
        """
        对话接口

        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大 token 数

        Returns:
            LLM 响应
        """
        return self.model.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
