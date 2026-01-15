"""
问答服务模块

解决什么问题:
1. 协调检索、Prompt 构建、LLM 调用的完整流程
2. 提供统一的问答接口
3. 记录问答日志，便于分析和优化

为什么现在需要:
- 问答是 RAG 对外的核心接口
- 多个模块协同工作，需要统一编排
- 日志记录是生产环境的基础能力
"""

from typing import List, Dict
from datetime import datetime
from sqlalchemy.orm import Session
from RagFlow.models.db_models import QALog
from RagFlow.models.qa import QARequest, QAResponse, QAErrorResponse, SourceDocument
from RagFlow.services.retriever import Retriever, RetrievedChunk
from RagFlow.services.prompt_builder import PromptBuilder
from RagFlow.services.llm import LLMService
from RagFlow.core.logger import get_logger

logger = get_logger(__name__)


class QAService:
    """问答服务"""

    def __init__(
        self,
        retriever: Retriever,
        prompt_builder: PromptBuilder,
        llm_service: LLMService,
        top_k: int = 5,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ):
        """
        初始化问答服务

        Args:
            retriever: 检索器实例
            prompt_builder: Prompt 构建器实例
            llm_service: LLM 服务实例
            top_k: 检索的文档数量
            temperature: 温度参数
            max_tokens: 最大 token 数
        """
        self.retriever = retriever
        self.prompt_builder = prompt_builder
        self.llm_service = llm_service
        self.top_k = top_k
        self.temperature = temperature
        self.max_tokens = max_tokens

    async def ask(
        self,
        request: QARequest,
        request_id: str,
        db: Session
    ) -> QAResponse:
        """
        回答用户问题

        Args:
            request: 问答请求
            request_id: 请求 ID
            db: 数据库会话

        Returns:
            问答响应
        """
        try:
            # 1. 检索相关文档
            retrieved_chunks = self.retriever.retrieve(
                question=request.question,
                top_k=request.top_k,
                db=db
            )

            # 2. 构建 Prompt
            context_chunks = [c.chunk_text for c in retrieved_chunks]
            messages = self.prompt_builder.build(
                context_chunks=context_chunks,
                question=request.question
            )

            # 3. 调用 LLM
            llm_response = self.llm_service.chat(
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )

            # 4. 构建来源信息
            sources = self._build_sources(retrieved_chunks, db)

            # 5. 构建响应
            response = QAResponse(
                request_id=request_id,
                answer=llm_response.content,
                sources=sources,
                prompt_tokens=llm_response.prompt_tokens,
                completion_tokens=llm_response.completion_tokens,
                total_tokens=llm_response.total_tokens,
                created_at=datetime.now()
            )

            # 6. 记录日志
            self._log_qa(
                db=db,
                request_id=request_id,
                question=request.question,
                answer=llm_response.content,
                sources=sources,
                prompt_tokens=llm_response.prompt_tokens,
                completion_tokens=llm_response.completion_tokens,
                total_tokens=llm_response.total_tokens
            )

            logger.info(f"问答完成，request_id: {request_id}")
            return response

        except Exception as e:
            logger.error(f"问答处理失败: {e}", exc_info=True)

            # 记录错误日志
            self._log_qa_error(
                db=db,
                request_id=request_id,
                question=request.question,
                error=str(e)
            )

            raise

    def _build_sources(
        self,
        retrieved_chunks: List[RetrievedChunk],
        db: Session
    ) -> List[SourceDocument]:
        """
        构建来源信息

        Args:
            retrieved_chunks: 检索到的切片
            db: 数据库会话

        Returns:
            来源文档列表
        """
        sources = []
        seen_document_ids = set()

        for chunk in retrieved_chunks:
            # 去重，每个文档只返回一次
            if chunk.document_id in seen_document_ids:
                continue

            seen_document_ids.add(chunk.document_id)

            sources.append(SourceDocument(
                document_id=chunk.document_id,
                file_name=chunk.file_name,
                chunk_index=chunk.chunk_index,
                similarity=chunk.similarity
            ))

        return sources

    def _log_qa(
        self,
        db: Session,
        request_id: str,
        question: str,
        answer: str,
        sources: List[SourceDocument],
        prompt_tokens: int = None,
        completion_tokens: int = None,
        total_tokens: int = None
    ):
        """记录问答日志"""
        try:
            import json

            qa_log = QALog(
                request_id=request_id,
                question=question,
                answer=answer,
                source_document_ids=json.dumps([s.dict() for s in sources], ensure_ascii=False),
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens
            )

            db.add(qa_log)
            db.commit()

        except Exception as e:
            logger.error(f"记录问答日志失败: {e}")

    def _log_qa_error(
        self,
        db: Session,
        request_id: str,
        question: str,
        error: str
    ):
        """记录问答错误日志"""
        try:
            qa_log = QALog(
                request_id=request_id,
                question=question,
                answer=None,
                source_document_ids=None,
                prompt_tokens=None,
                completion_tokens=None,
                total_tokens=None,
                error_message=error
            )

            db.add(qa_log)
            db.commit()

        except Exception as e:
            logger.error(f"记录问答错误日志失败: {e}")
