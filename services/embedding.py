"""
文本 Embedding 模块

解决什么问题:
1. 将文本转换为向量表示，用于语义检索
2. 统一 Embedding 接口，便于替换不同模型
3. 提供批处理能力，提高效率

为什么现在需要:
- 向量检索是 RAG 的核心能力
- Embedding 模型需要统一封装，避免散落在各处
- 批处理可以显著提升性能
"""

from typing import List
from abc import ABC, abstractmethod
import numpy as np
from RagFlow.core.logger import get_logger

logger = get_logger(__name__)


class EmbeddingModel(ABC):
    """Embedding 模型抽象基类"""

    @abstractmethod
    def embed(self, text: str) -> List[float]:
        """
        对单个文本进行 Embedding

        Args:
            text: 输入文本

        Returns:
            向量表示
        """
        pass

    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        批量 Embedding

        Args:
            texts: 输入文本列表

        Returns:
            向量列表
        """
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        """返回向量维度"""
        pass


class SentenceTransformerEmbedding(EmbeddingModel):
    """基于 Sentence-Transformers 的 Embedding 模型"""

    def __init__(self, model_name: str = "shibing624/text2vec-base-chinese", cache_dir: str = None):
        """
        初始化 Embedding 模型

        Args:
            model_name: 模型名称或路径
            cache_dir: 模型缓存目录（可选）
        """
        try:
            from sentence_transformers import SentenceTransformer

            # 设置缓存目录
            if cache_dir:
                import os
                os.environ['HF_HOME'] = cache_dir

            self.model = SentenceTransformer(model_name)
            self._dimension = self.model.get_sentence_embedding_dimension()
            logger.info(f"加载 Embedding 模型成功: {model_name}, 维度: {self._dimension}")
            if cache_dir:
                logger.info(f"模型缓存目录: {cache_dir}")
        except Exception as e:
            logger.error(f"加载 Embedding 模型失败: {e}")
            raise

    def embed(self, text: str) -> List[float]:
        """对单个文本进行 Embedding"""
        if not text or not text.strip():
            return [0.0] * self.dimension

        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """批量 Embedding"""
        if not texts:
            return []

        # 过滤空文本
        valid_texts = [t for t in texts if t and t.strip()]
        if not valid_texts:
            return [[0.0] * self.dimension] * len(texts)

        embeddings = self.model.encode(valid_texts, convert_to_numpy=True)
        return embeddings.tolist()

    @property
    def dimension(self) -> int:
        """返回向量维度"""
        return self._dimension


class EmbeddingService:
    """Embedding 服务封装"""

    def __init__(self, model: EmbeddingModel):
        """
        初始化 Embedding 服务

        Args:
            model: Embedding 模型实例
        """
        self.model = model

    def embed(self, text: str) -> List[float]:
        """
        对单个文本进行 Embedding

        Args:
            text: 输入文本

        Returns:
            向量表示
        """
        return self.model.embed(text)

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        批量 Embedding

        Args:
            texts: 输入文本列表

        Returns:
            向量列表
        """
        return self.model.embed_batch(texts)

    @property
    def dimension(self) -> int:
        """返回向量维度"""
        return self.model.dimension
