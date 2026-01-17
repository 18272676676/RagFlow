"""
向量库模块

解决什么问题:
1. 存储和检索文本向量，支持相似度搜索
2. 抽象向量库接口，便于替换不同实现
3. 提供统一的 CRUD 操作接口

为什么现在需要:
- 向量检索是 RAG 的核心能力
- 需要抽象接口，便于从 FAISS 迁移到 Milvus/Chroma
- 统一接口降低模块间耦合
"""

from typing import List, Dict, Optional
from abc import ABC, abstractmethod
from dataclasses import dataclass
import numpy as np
from pathlib import Path
import pickle
from RagFlow.core.logger import get_logger

logger = get_logger(__name__)

logger = get_logger(__name__)


@dataclass
class SearchResult:
    """搜索结果"""
    chunk_id: int
    document_id: int
    chunk_index: int
    chunk_text: str
    similarity: float


class VectorStore(ABC):
    """向量库抽象基类"""

    @abstractmethod
    def add_documents(
        self,
        documents: List[Dict],
        embeddings: List[List[float]]
    ) -> None:
        """
        添加文档向量

        Args:
            documents: 文档列表，每个文档包含 id, document_id, chunk_index, chunk_text
            embeddings: 对应的向量列表
        """
        pass

    @abstractmethod
    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5
    ) -> List[SearchResult]:
        """
        相似度搜索

        Args:
            query_embedding: 查询向量
            top_k: 返回前 K 个结果

        Returns:
            搜索结果列表
        """
        pass

    @abstractmethod
    def delete_by_document_id(self, document_id: int) -> None:
        """
        删除指定文档的所有向量

        Args:
            document_id: 文档 ID
        """
        pass

    @abstractmethod
    def clear(self) -> None:
        """清空所有向量"""
        pass


class FAISSVectorStore(VectorStore):
    """基于 FAISS 的向量库实现"""

    def __init__(self, index_path: str = "./data/vector_store/faiss_index"):
        """
        初始化 FAISS 向量库

        Args:
            index_path: FAISS 索引文件路径
        """
        self.index_path = Path(index_path)
        self.index_path.mkdir(parents=True, exist_ok=True)

        self.index = None
        self.documents = []

        self._load_index()

    def _load_index(self):
        """加载已有索引"""
        index_file = self.index_path / "index.faiss"
        docs_file = self.index_path / "documents.pkl"

        if index_file.exists() and docs_file.exists():
            # 检查文件大小，避免加载损坏的空文件
            if index_file.stat().st_size == 0 or docs_file.stat().st_size == 0:
                logger.warning(f"索引文件损坏或为空，将重新初始化: index={index_file.stat().st_size}B, docs={docs_file.stat().st_size}B")
                self._init_index()
                return

            try:
                import faiss

                self.index = faiss.read_index(str(index_file))
                with open(docs_file, "rb") as f:
                    self.documents = pickle.load(f)
                logger.info(f"加载 FAISS 索引成功，包含 {self.index.ntotal} 个向量")
            except Exception as e:
                logger.error(f"加载 FAISS 索引失败: {e}，将重新初始化索引")
                self._init_index()
        else:
            self._init_index()

    def _init_index(self):
        """初始化索引"""
        self.index = None
        self.documents = []
        logger.info("初始化新的 FAISS 索引")

    def _save_index(self):
        """保存索引"""
        if self.index is None:
            return

        try:
            import faiss

            index_file = self.index_path / "index.faiss"
            docs_file = self.index_path / "documents.pkl"

            faiss.write_index(self.index, str(index_file))
            with open(docs_file, "wb") as f:
                pickle.dump(self.documents, f)

            logger.info(f"保存 FAISS 索引成功，包含 {self.index.ntotal} 个向量")
        except Exception as e:
            logger.error(f"保存 FAISS 索引失败: {e}")

    def add_documents(
        self,
        documents: List[Dict],
        embeddings: List[List[float]]
    ) -> None:
        """添加文档向量"""
        if not documents or not embeddings:
            return

        import faiss

        embeddings_array = np.array(embeddings, dtype=np.float32)
        dimension = embeddings_array.shape[1]

        if self.index is None:
            # 使用余弦相似度：先归一化向量，再使用内积
            # IndexFlatIP 使用归一化向量时等于余弦相似度
            self.index = faiss.IndexFlatIP(dimension)

        # 归一化向量以获得余弦相似度（范围 -1 到 1）
        faiss.normalize_L2(embeddings_array)
        self.index.add(embeddings_array)

        start_id = len(self.documents)
        for i, doc in enumerate(documents):
            self.documents.append({
                "id": start_id + i,
                **doc
            })

        logger.info(f"添加 {len(documents)} 个文档向量")
        self._save_index()

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5
    ) -> List[SearchResult]:
        """相似度搜索"""
        # 每次搜索前重新加载索引，确保获取最新数据
        self._load_index()

        if self.index is None or self.index.ntotal == 0:
            return []

        import faiss

        query_array = np.array([query_embedding], dtype=np.float32)
        # 归一化查询向量以获得余弦相似度
        faiss.normalize_L2(query_array)
        similarities, indices = self.index.search(query_array, top_k)

        results = []
        for similarity, idx in zip(similarities[0], indices[0]):
            if idx == -1 or idx >= len(self.documents):
                continue

            doc = self.documents[idx]

            # 确保document_id是整数
            doc_id = doc.get("document_id")
            if doc_id is not None:
                try:
                    doc_id = int(doc_id)
                except (ValueError, TypeError):
                    logger.error(f"无法将document_id转换为整数: {doc_id} (type: {type(doc_id).__name__})")
                    logger.error(f"原始文档数据: {doc}")
                    continue

            results.append(SearchResult(
                chunk_id=int(doc.get("id", idx)),
                document_id=doc_id,
                chunk_index=int(doc.get("chunk_index", 0)),
                chunk_text=doc.get("chunk_text", ""),
                similarity=float(similarity)
            ))

        logger.info(f"向量搜索完成，返回 {len(results)} 个结果")
        return results

    def delete_by_document_id(self, document_id: int) -> None:
        """删除指定文档的所有向量"""
        new_documents = [doc for doc in self.documents if doc["document_id"] != document_id]

        if len(new_documents) == len(self.documents):
            return

        self._init_index()
        self._save_index()

        logger.warning(f"FAISS 删除文档 {document_id} 需要重建索引")

    def clear(self) -> None:
        """清空所有向量"""
        self._init_index()
        self._save_index()
        logger.info("清空 FAISS 索引")


class VectorStoreFactory:
    """向量库工厂"""

    @staticmethod
    def create_vector_store(
        store_type: str = "faiss",
        **kwargs
    ) -> VectorStore:
        """创建向量库实例"""
        if store_type == "faiss":
            return FAISSVectorStore(**kwargs)
        else:
            raise ValueError(f"不支持的向量库类型: {store_type}")
