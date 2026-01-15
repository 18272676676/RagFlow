"""
检索模块

解决什么问题:
1. 根据用户问题检索相关文档切片
2. 支持 Top-K 相似度搜索
3. 返回命中的文档来源信息

为什么现在需要:
- 检索是 RAG 的核心能力
- 用户需要知道答案来源，增加可信度
- 独立检索模块便于优化和替换算法
"""

from typing import List
from sqlalchemy.orm import Session
from RagFlow.models.db_models import Document, Chunk
from RagFlow.services.embedding import EmbeddingService
from RagFlow.services.vector_store import VectorStore, SearchResult
from RagFlow.core.logger import get_logger

logger = get_logger(__name__)


class RetrievedChunk:
    """检索到的切片"""

    def __init__(
        self,
        chunk_id: int,
        document_id: int,
        file_name: str,
        chunk_index: int,
        chunk_text: str,
        similarity: float
    ):
        self.chunk_id = chunk_id
        self.document_id = document_id
        self.file_name = file_name
        self.chunk_index = chunk_index
        self.chunk_text = chunk_text
        self.similarity = similarity


class Retriever:
    """检索器"""

    def __init__(
        self,
        vector_store: VectorStore,
        embedding_service: EmbeddingService
    ):
        """
        初始化检索器

        Args:
            vector_store: 向量库实例
            embedding_service: Embedding 服务实例
        """
        self.vector_store = vector_store
        self.embedding_service = embedding_service

    def retrieve(
        self,
        question: str,
        top_k: int = 5,
        db: Session = None
    ) -> List[RetrievedChunk]:
        """
        检索相关文档切片

        Args:
            question: 用户问题
            top_k: 返回前 K 个结果
            db: 数据库会话（用于获取文件名）

        Returns:
            检索到的切片列表
        """
        # 1. 对问题进行 Embedding
        question_embedding = self.embedding_service.embed(question)
        logger.info(f"问题 Embedding 完成，向量维度: {len(question_embedding)}")

        # 2. 向量相似度搜索
        search_results = self.vector_store.search(question_embedding, top_k)
        logger.info(f"检索到 {len(search_results)} 个相关切片")

        if not search_results:
            return []

        # 3. 补充文档信息（如文件名）
        retrieved_chunks = []

        if db:
            # 获取文档 ID 列表
            document_ids = list(set(r.document_id for r in search_results))

            # 查询文档信息
            documents = db.query(Document).filter(
                Document.id.in_(document_ids)
            ).all()

            # 构建 ID 到文档的映射
            document_map = {doc.id: doc for doc in documents}

            # 组装结果
            for result in search_results:
                doc = document_map.get(result.document_id)
                if doc:
                    retrieved_chunks.append(RetrievedChunk(
                        chunk_id=result.chunk_id,
                        document_id=result.document_id,
                        file_name=doc.file_name,
                        chunk_index=result.chunk_index,
                        chunk_text=result.chunk_text,
                        similarity=result.similarity
                    ))
        else:
            # 无数据库会话，直接使用搜索结果
            for result in search_results:
                retrieved_chunks.append(RetrievedChunk(
                    chunk_id=result.chunk_id,
                    document_id=result.document_id,
                    file_name="",
                    chunk_index=result.chunk_index,
                    chunk_text=result.chunk_text,
                    similarity=result.similarity
                ))

        return retrieved_chunks
