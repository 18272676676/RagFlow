"""
问答领域模型

解决什么问题:
1. 定义问答相关的数据结构
2. 提供类型检查和数据验证
3. 明确问答请求和响应的数据格式

为什么现在需要:
- 需要清晰的问答接口定义
- 支持多轮对话场景
- 便于后续扩展（如添加对话历史等）
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class SourceDocument(BaseModel):
    """来源文档信息"""
    document_id: int
    file_name: str
    chunk_index: int
    similarity: float


class QARequest(BaseModel):
    """问答请求模型"""
    question: str = Field(..., min_length=1, max_length=1000, description="用户问题")
    top_k: Optional[int] = Field(default=5, ge=1, le=20, description="检索的文档数量")


class QAResponse(BaseModel):
    """问答响应模型"""
    request_id: str
    answer: str
    sources: List[SourceDocument]
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    created_at: datetime
    answer_source: Optional[str] = Field(default="knowledge_base", description="答案来源: knowledge_base(知识库) / llm(大模型)")


class QAErrorResponse(BaseModel):
    """问答错误响应模型"""
    request_id: str
    error: str
    error_type: str
    created_at: datetime
