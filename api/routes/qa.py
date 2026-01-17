"""
问答 API 路由

解决什么问题:
1. 提供问答的 HTTP 接口
2. 处理用户问题并返回答案
3. 返回答案来源信息
4. 支持会话历史

为什么现在需要:
- 需要通过 HTTP 接口与前端交互
- 问答是 RAG 对外提供的核心能力
- API 层隔离业务逻辑，提高可测试性
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from contextvars import copy_context
import uuid

from RagFlow.core.database import get_db
from RagFlow.core.logger import get_logger, set_request_id
from RagFlow.core.auth import get_current_active_user
from RagFlow.models.db_models import User, Conversation, Message
from RagFlow.models.qa import QARequest, QAResponse
from RagFlow.services.qa_service import QAService
from RagFlow.services.retriever import Retriever
from RagFlow.services.prompt_builder import PromptBuilderFactory
from RagFlow.services.llm import LLMService, DeepSeekLLM
from RagFlow.services.embedding import EmbeddingService, SentenceTransformerEmbedding
from RagFlow.services.vector_store import VectorStoreFactory
from RagFlow.api.routes.conversation import create_message as add_message_to_conversation
from RagFlow.config.settings import settings

logger = get_logger(__name__)

# 创建路由器
router = APIRouter(prefix="/api/qa", tags=["问答"])

# 初始化服务（生产环境应该通过依赖注入）
_vector_store = VectorStoreFactory.create_vector_store(
    store_type=settings.VECTOR_DB_TYPE,
    index_path=settings.FAISS_INDEX_PATH
)

_embedding_model = SentenceTransformerEmbedding(
    model_name=settings.EMBEDDING_MODEL,
    cache_dir=getattr(settings, 'EMBEDDING_CACHE_DIR', None)
)
_embedding_service = EmbeddingService(_embedding_model)

_retriever = Retriever(
    vector_store=_vector_store,
    embedding_service=_embedding_service
)

_prompt_builder = PromptBuilderFactory.create_default()

_llm_model = DeepSeekLLM(
    api_base=settings.DEEPSEEK_API_BASE,
    api_key=settings.DEEPSEEK_API_KEY,
    model=settings.DEEPSEEK_MODEL
)
_llm_service = LLMService(_llm_model)

_qa_service = QAService(
    retriever=_retriever,
    prompt_builder=_prompt_builder,
    llm_service=_llm_service,
    top_k=settings.TOP_K,
    temperature=settings.TEMPERATURE,
    max_tokens=settings.MAX_TOKENS,
    similarity_threshold=getattr(settings, 'SIMILARITY_THRESHOLD', 0.3)
)


@router.post("/ask", response_model=QAResponse)
async def ask_question(
    request: QARequest,
    conversation_id: int = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    问答接口

    基于知识库回答用户问题，流程：
    1. 检索相关文档切片
    2. 构建 Prompt（包含上下文）
    3. 调用 LLM 生成答案
    4. 返回答案和来源信息
    5. 记录到会话历史
    """
    # 设置请求 ID
    request_id = uuid.uuid4().hex
    set_request_id(request_id)

    logger.info(f"收到问答请求: {request.question}")

    # 如果提供了会话ID，验证会话是否存在
    conversation = None
    if conversation_id:
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id
        ).first()
        if not conversation:
            raise HTTPException(status_code=404, detail="会话不存在")

    try:
        # 调用问答服务
        response = await _qa_service.ask(
            request=request,
            request_id=request_id,
            db=db
        )

        # 保存消息到会话
        if conversation:
            conv_id = conversation.id  # 使用 conversation 对象的 id
            user_message = Message(
                conversation_id=conv_id,
                role="user",
                content=request.question
            )
            db.add(user_message)

            # 保存助手回复到会话
            assistant_message = Message(
                conversation_id=conv_id,
                role="assistant",
                content=response.answer
            )
            db.add(assistant_message)
            db.commit()
        else:
            logger.info(f"没有提供 conversation_id，消息未保存到会话")

        logger.info(f"问答成功，request_id: {request_id}")
        return response

    except Exception as e:
        logger.error(f"问答失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"问答处理失败: {str(e)}"
        )


@router.get("/health")
async def health_check():
    """健康检查接口"""
    return {
        "status": "ok",
        "services": {
            "vector_store": "ok",
            "embedding": "ok",
            "llm": "ok"
        }
    }
