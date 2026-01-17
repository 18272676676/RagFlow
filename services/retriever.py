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

        # 打印搜索结果，调试用
        logger.debug(f"搜索结果详情:")
        for result in search_results:
            logger.debug(f"  - chunk_id: {result.chunk_id} (type: {type(result.chunk_id)}), document_id: {result.document_id} (type: {type(result.document_id)})")

        # 3. 补充文档信息（如文件名）
        retrieved_chunks = []

        if db:
            # 获取文档 ID 列表 - 确保转换为整数
            document_ids = []
            for r in search_results:
                if r.document_id is not None:
                    try:
                        doc_id = int(r.document_id)
                        document_ids.append(doc_id)
                        logger.debug(f"转换 document_id: {r.document_id} ({type(r.document_id).__name__}) -> {doc_id} (int)")
                    except (ValueError, TypeError) as e:
                        logger.error(f"无法转换 document_id: {r.document_id} (type: {type(r.document_id).__name__}), error: {e}")
                        logger.error(f"完整的搜索结果: {r.__dict__}")

            document_ids = list(set(document_ids))
            logger.info(f"查询文档信息，IDs: {document_ids}")

            if not document_ids:
                logger.warning("没有有效的 document_id")
                return []

            # 查询文档信息
            documents = db.query(Document).filter(
                Document.id.in_(document_ids)
            ).all()

            logger.info(f"查询到 {len(documents)} 个文档记录")

            # 构建 ID 到文档的映射
            document_map = {doc.id: doc for doc in documents}

            # 组装结果
            for result in search_results:
                doc_id = int(result.document_id) if result.document_id is not None else None
                if doc_id is None:
                    logger.warning(f"搜索结果缺少 document_id，跳过")
                    continue

                doc = document_map.get(doc_id)
                if doc:
                    retrieved_chunks.append(RetrievedChunk(
                        chunk_id=result.chunk_id,
                        document_id=doc_id,
                        file_name=doc.file_name,
                        chunk_index=result.chunk_index,
                        chunk_text=result.chunk_text,
                        similarity=result.similarity
                    ))
                else:
                    logger.warning(f"文档 ID {doc_id} 在数据库中不存在")
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
