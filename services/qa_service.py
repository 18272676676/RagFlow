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
from datetime import datetime, timezone, timedelta
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
        max_tokens: int = 2000,
        similarity_threshold: float = 0.3  # 相似度阈值，低于此值认为知识库中没有相关内容
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
            similarity_threshold: 相似度阈值，低于此值认为知识库中没有相关内容
        """
        self.retriever = retriever
        self.prompt_builder = prompt_builder
        self.llm_service = llm_service
        self.top_k = top_k
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.similarity_threshold = similarity_threshold

    async def ask(
        self,
        request: QARequest,
        request_id: str,
        db: Session,
        knowledge_base_id: int = None
    ) -> QAResponse:
        """
        回答用户问题

        Args:
            request: 问答请求
            request_id: 请求 ID
            db: 数据库会话
            knowledge_base_id: 知识库 ID（可选，如果指定则只从该知识库检索）

        Returns:
            问答响应
        """
        try:
            logger.info(f"开始处理问答，request_id: {request_id}, 问题: {request.question}, knowledge_base_id: {knowledge_base_id}")

            # 1. 检索相关文档
            retrieved_chunks = self.retriever.retrieve(
                question=request.question,
                top_k=request.top_k,
                knowledge_base_id=knowledge_base_id,
                db=db
            )

            logger.info(f"检索到 {len(retrieved_chunks)} 个相关切片")

            # 判断是否使用知识库（基于相似度阈值）
            use_knowledge_base = False
            answer_source = "llm"  # 默认使用大模型
            sources = []
            prompt_hint = ""  # 提示信息

            if retrieved_chunks:
                # 获取最高相似度
                max_similarity = max(chunk.similarity for chunk in retrieved_chunks)
                logger.info(f"最高相似度: {max_similarity:.4f}, 阈值: {self.similarity_threshold}")

                # 如果最高相似度超过阈值，使用知识库
                if max_similarity >= self.similarity_threshold:
                    use_knowledge_base = True
                    answer_source = "knowledge_base"
                    sources = self._build_sources(retrieved_chunks, db)
                    logger.info(f"相似度 {max_similarity:.4f} >= 阈值 {self.similarity_threshold}，使用知识库")
                else:
                    logger.info(f"相似度 {max_similarity:.4f} < 阈值 {self.similarity_threshold}，不使用知识库")
            else:
                logger.info("检索结果为空，不使用知识库")

            # 2. 根据判断结果构建 Prompt
            if use_knowledge_base:
                # 使用知识库上下文
                context_chunks = [c.chunk_text for c in retrieved_chunks]
                messages = self.prompt_builder.build(
                    context_chunks=context_chunks,
                    question=request.question
                )
                logger.info("使用知识库上下文构建 Prompt")
            else:
                # 不使用知识库，直接让大模型回答
                messages = self.prompt_builder.build_without_context(question=request.question)
                prompt_hint = "知识库中没有找到相关的答案，以下是可以借鉴的答案"
                logger.info("不使用知识库，直接调用大模型回答")

            # 3. 调用 LLM
            logger.info(f"开始调用 LLM...")
            llm_response = self.llm_service.chat(
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )

            logger.info(f"LLM 返回答案: {llm_response.content[:100]}...")

            # 4. 构建响应
            # 如果是 llm 模式，添加提示前缀
            final_answer = f"{prompt_hint}\n\n{llm_response.content}" if prompt_hint else llm_response.content

            response = QAResponse(
                request_id=request_id,
                answer=final_answer,
                sources=sources,
                prompt_tokens=llm_response.prompt_tokens,
                completion_tokens=llm_response.completion_tokens,
                total_tokens=llm_response.total_tokens,
                created_at=datetime.now(),  # 数据库连接已设置时区，使用服务器时间
                answer_source=answer_source
            )

            # 6. 记录日志
            self._log_qa(
                db=db,
                request_id=request_id,
                question=request.question,
                answer=llm_response.content,  # 记录原始答案
                sources=sources,
                prompt_tokens=llm_response.prompt_tokens,
                completion_tokens=llm_response.completion_tokens,
                total_tokens=llm_response.total_tokens
            )

            logger.info(f"问答完成，request_id: {request_id}, answer_source: {answer_source}")
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

            # 添加调试日志
            logger.debug(f"构建来源 - document_id: {chunk.document_id} (type: {type(chunk.document_id)}), file_name: {chunk.file_name}")

            # 确保document_id是整数
            doc_id = chunk.document_id
            if doc_id is not None:
                try:
                    doc_id = int(doc_id)
                except (ValueError, TypeError) as e:
                    logger.error(f"document_id转换失败: {doc_id} (type: {type(doc_id)}), error: {e}")
                    continue

            sources.append(SourceDocument(
                document_id=doc_id,
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

            # 确保source中的document_id是整数
            sources_data = []
            for s in sources:
                sources_data.append({
                    "document_id": int(s.document_id) if s.document_id is not None else None,
                    "file_name": str(s.file_name),
                    "chunk_index": int(s.chunk_index),
                    "similarity": float(s.similarity)
                })

            qa_log = QALog(
                request_id=request_id,
                question=question,
                answer=answer,
                source_document_ids=json.dumps(sources_data, ensure_ascii=False),
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
