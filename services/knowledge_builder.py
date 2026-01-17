"""
知识构建模块

解决什么问题:
1. 协调文档解析、分块、Embedding、向量存储的完整流程
2. 提供统一的知识构建接口
3. 处理知识构建过程中的异常和状态更新

为什么现在需要:
- 知识构建是 RAG 的核心业务流程，需要独立管理
- 多个模块协同工作，需要统一编排
- 状态管理确保构建过程的可追溯性
"""

from typing import Optional, List
from sqlalchemy.orm import Session
from pathlib import Path
import aiofiles
from RagFlow.models.db_models import Document, Chunk
from RagFlow.services.document_parser import DocumentParserFactory
from RagFlow.services.chunker import Chunker
from RagFlow.services.embedding import EmbeddingService, SentenceTransformerEmbedding
from RagFlow.services.vector_store import VectorStore, VectorStoreFactory
from RagFlow.core.logger import get_logger
from RagFlow.config.settings import settings

logger = get_logger(__name__)


class KnowledgeBuilder:
    """知识构建器"""

    def __init__(
        self,
        upload_dir: str = "./data/uploads",
        vector_store: Optional[VectorStore] = None,
        embedding_service: Optional[EmbeddingService] = None,
        chunker: Optional[Chunker] = None
    ):
        """
        初始化知识构建器

        Args:
            upload_dir: 文件上传目录
            vector_store: 向量库实例
            embedding_service: Embedding 服务实例
            chunker: 分块器实例
        """
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

        # 初始化各组件
        self.vector_store = vector_store or VectorStoreFactory.create_vector_store(
            store_type=settings.VECTOR_DB_TYPE,
            index_path=settings.FAISS_INDEX_PATH
        )

        embedding_model = SentenceTransformerEmbedding(
            model_name=settings.EMBEDDING_MODEL,
            cache_dir=getattr(settings, 'EMBEDDING_CACHE_DIR', None)
        )
        self.embedding_service = embedding_service or EmbeddingService(embedding_model)

        self.chunker = chunker or Chunker(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP
        )

    async def build_knowledge(
        self,
        document_id: int,
        file_path: str,
        file_name: str,
        db: Session,
        cleanup_temp_file: bool = False
    ) -> bool:
        """
        构建知识库

        Args:
            document_id: 文档 ID
            file_path: 文件路径
            file_name: 文件名
            db: 数据库会话
            cleanup_temp_file: 是否清理临时文件

        Returns:
            是否构建成功
        """
        try:
            # 更新状态为处理中
            self._update_document_status(db, document_id, "processing")

            # 1. 解析文档
            text = await self._parse_document(file_path, file_name)
            if not text:
                raise ValueError("文档解析失败或内容为空")

            # 2. 分块
            chunks = self.chunker.chunk(text)
            logger.info(f"文档 {file_name} 分块完成，共 {len(chunks)} 个块")

            # 3. 保存切片到数据库
            chunk_embeddings = []
            chunk_documents = []

            for chunk in chunks:
                # 保存到数据库
                db_chunk = Chunk(
                    document_id=document_id,
                    chunk_index=chunk.index,
                    chunk_text=chunk.text
                )
                db.add(db_chunk)
                db.flush()  # 获取 ID

                # 准备向量数据
                chunk_embeddings.append(chunk.text)
                chunk_documents.append({
                    "document_id": document_id,
                    "chunk_index": chunk.index,
                    "chunk_text": chunk.text
                })

            # 4. 计算 Embedding
            embeddings = self.embedding_service.embed_batch(chunk_embeddings)
            logger.info(f"计算 Embedding 完成，向量维度: {len(embeddings[0])}")

            # 5. 存储到向量库
            self.vector_store.add_documents(chunk_documents, embeddings)

            # 6. 更新状态为完成
            self._update_document_status(
                db,
                document_id,
                "completed",
                chunk_count=len(chunks)
            )

            db.commit()
            logger.info(f"文档 {file_name} 知识构建完成")

            # 如果是临时文件，删除它
            if cleanup_temp_file and file_path:
                try:
                    import os
                    if os.path.exists(file_path):
                        os.unlink(file_path)
                        logger.info(f"已删除临时文件: {file_path}")
                except Exception as e:
                    logger.warning(f"删除临时文件失败: {e}")

            return True

        except Exception as e:
            logger.error(f"知识构建失败: {e}", exc_info=True)
            self._update_document_status(
                db,
                document_id,
                "failed",
                error_message=str(e)
            )
            db.commit()

            # 如果是临时文件且构建失败，也要删除
            if cleanup_temp_file and file_path:
                try:
                    import os
                    if os.path.exists(file_path):
                        os.unlink(file_path)
                        logger.info(f"已删除临时文件: {file_path}")
                except Exception as e:
                    logger.warning(f"删除临时文件失败: {e}")

            return False

    async def build_knowledge_from_content(
        self,
        document_id: int,
        file_content: bytes,
        file_name: str,
        file_ext: str,
        storage_path: str,
        db: Session
    ) -> bool:
        """
        直接从内存中的文件内容构建知识库（无需读取文件）

        Args:
            document_id: 文档 ID
            file_content: 文件内容（bytes）
            file_name: 文件名
            file_ext: 文件扩展名（带点，如 .docx）
            storage_path: 存储路径（用于元数据）
            db: 数据库会话

        Returns:
            是否构建成功
        """
        try:
            # 更新状态为处理中
            self._update_document_status(db, document_id, "processing")

            # 1. 解析文档（从内存中的bytes直接解析）
            if not DocumentParserFactory.is_supported(file_name):
                raise ValueError(f"不支持的文件类型: {file_name}")

            parser = DocumentParserFactory.get_parser(file_name)
            text = parser.parse(file_content)

            if not text:
                raise ValueError("文档解析失败或内容为空")

            logger.info(f"文档 {file_name} 解析成功，内容长度: {len(text)}")

            # 2. 分块
            chunks = self.chunker.chunk(text)
            logger.info(f"文档 {file_name} 分块完成，共 {len(chunks)} 个块")

            # 3. 保存切片到数据库
            chunk_embeddings = []
            chunk_documents = []

            for chunk in chunks:
                # 保存到数据库
                db_chunk = Chunk(
                    document_id=document_id,
                    chunk_index=chunk.index,
                    chunk_text=chunk.text
                )
                db.add(db_chunk)
                db.flush()  # 获取 ID

                # 准备向量数据
                chunk_embeddings.append(chunk.text)
                chunk_documents.append({
                    "document_id": document_id,
                    "chunk_index": chunk.index,
                    "chunk_text": chunk.text
                })

            # 4. 计算 Embedding
            embeddings = self.embedding_service.embed_batch(chunk_embeddings)
            logger.info(f"计算 Embedding 完成，向量维度: {len(embeddings[0])}")

            # 5. 存储到向量库
            self.vector_store.add_documents(chunk_documents, embeddings)

            # 6. 更新状态为完成
            self._update_document_status(
                db,
                document_id,
                "completed",
                chunk_count=len(chunks)
            )

            db.commit()
            logger.info(f"文档 {file_name} 知识构建完成")
            return True

        except Exception as e:
            logger.error(f"知识构建失败: {e}", exc_info=True)
            self._update_document_status(
                db,
                document_id,
                "failed",
                error_message=str(e)
            )
            db.commit()
            return False
        """
        构建知识库

        Args:
            document_id: 文档 ID
            file_path: 文件路径
            file_name: 文件名
            db: 数据库会话

        Returns:
            是否构建成功
        """
        try:
            # 更新状态为处理中
            self._update_document_status(db, document_id, "processing")

            # 1. 解析文档
            text = await self._parse_document(file_path, file_name)
            if not text:
                raise ValueError("文档解析失败或内容为空")

            # 2. 分块
            chunks = self.chunker.chunk(text)
            logger.info(f"文档 {file_name} 分块完成，共 {len(chunks)} 个块")

            # 3. 保存切片到数据库
            chunk_embeddings = []
            chunk_documents = []

            for chunk in chunks:
                # 保存到数据库
                db_chunk = Chunk(
                    document_id=document_id,
                    chunk_index=chunk.index,
                    chunk_text=chunk.text
                )
                db.add(db_chunk)
                db.flush()  # 获取 ID

                # 准备向量数据
                chunk_embeddings.append(chunk.text)
                chunk_documents.append({
                    "document_id": document_id,
                    "chunk_index": chunk.index,
                    "chunk_text": chunk.text
                })

            # 4. 计算 Embedding
            embeddings = self.embedding_service.embed_batch(chunk_embeddings)
            logger.info(f"计算 Embedding 完成，向量维度: {len(embeddings[0])}")

            # 5. 存储到向量库
            self.vector_store.add_documents(chunk_documents, embeddings)

            # 6. 更新状态为完成
            self._update_document_status(
                db,
                document_id,
                "completed",
                chunk_count=len(chunks)
            )

            db.commit()
            logger.info(f"文档 {file_name} 知识构建完成")

            # 如果是临时文件，删除它
            if cleanup_temp_file and file_path:
                try:
                    import os
                    if os.path.exists(file_path):
                        os.unlink(file_path)
                        logger.info(f"已删除临时文件: {file_path}")
                except Exception as e:
                    logger.warning(f"删除临时文件失败: {e}")

            return True

        except Exception as e:
            logger.error(f"知识构建失败: {e}", exc_info=True)
            self._update_document_status(
                db,
                document_id,
                "failed",
                error_message=str(e)
            )
            db.commit()

            # 如果是临时文件且构建失败，也要删除
            if cleanup_temp_file and file_path:
                try:
                    import os
                    if os.path.exists(file_path):
                        os.unlink(file_path)
                        logger.info(f"已删除临时文件: {file_path}")
                except Exception as e:
                    logger.warning(f"删除临时文件失败: {e}")

            return False

    async def _parse_document(self, file_path: str, file_name: str) -> str:
        """
        解析文档

        Args:
            file_path: 文件路径
            file_name: 文件名

        Returns:
            解析后的文本
        """
        # 检查文件类型是否支持
        if not DocumentParserFactory.is_supported(file_name):
            raise ValueError(f"不支持的文件类型: {file_name}")

        # 获取解析器
        parser = DocumentParserFactory.get_parser(file_name)

        # 读取文件内容
        async with aiofiles.open(file_path, 'rb') as f:
            file_content = await f.read()

        # 解析文档
        return parser.parse(file_content)

    def _update_document_status(
        self,
        db: Session,
        document_id: int,
        status: str,
        chunk_count: Optional[int] = None,
        error_message: Optional[str] = None
    ):
        """
        更新文档状态

        Args:
            db: 数据库会话
            document_id: 文档 ID
            status: 状态
            chunk_count: 切片数量
            error_message: 错误信息
        """
        document = db.query(Document).filter(Document.id == document_id).first()
        if document:
            document.status = status
            if chunk_count is not None:
                document.chunk_count = chunk_count
            if error_message is not None:
                document.error_message = error_message
            db.flush()

    def delete_document(self, document_id: int, db: Session) -> bool:
        """
        删除文档及其相关知识

        Args:
            document_id: 文档 ID
            db: 数据库会话

        Returns:
            是否删除成功
        """
        try:
            # 删除向量库中的数据
            self.vector_store.delete_by_document_id(document_id)

            # 删除数据库中的切片
            db.query(Chunk).filter(Chunk.document_id == document_id).delete()

            # 删除文档记录
            document = db.query(Document).filter(Document.id == document_id).first()
            if document:
                # 删除文件
                file_path = Path(document.file_path)
                if file_path.exists():
                    file_path.unlink()

                db.delete(document)

            db.commit()
            logger.info(f"文档 {document_id} 删除成功")
            return True

        except Exception as e:
            logger.error(f"删除文档失败: {e}", exc_info=True)
            db.rollback()
            return False
