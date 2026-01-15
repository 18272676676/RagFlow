"""
文档领域模型

解决什么问题:
1. 定义文档相关的数据结构，统一数据格式
2. 提供类型检查和数据验证
3. 隔离数据库模型与 API 模型

为什么现在需要:
- 需要明确的数据结构定义，避免"字典传参"导致的维护困难
- 数据验证在业务逻辑之前完成，减少无效数据处理
- 为后续的数据迁移和扩展提供基础
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class DocumentStatus(str, Enum):
    """文档状态枚举"""
    PENDING = "pending"  # 待处理
    PROCESSING = "processing"  # 处理中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 失败


class DocumentUploadRequest(BaseModel):
    """文档上传请求模型"""
    pass  # 实际通过 UploadFile 处理


class DocumentResponse(BaseModel):
    """文档响应模型"""
    id: int
    file_name: str
    file_path: str
    file_size: int
    file_type: str
    status: DocumentStatus
    chunk_count: int = 0
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ChunkResponse(BaseModel):
    """文档切片响应模型"""
    id: int
    document_id: int
    chunk_index: int
    chunk_text: str
    created_at: datetime

    class Config:
        from_attributes = True


class SearchResponse(BaseModel):
    """搜索结果响应模型"""
    id: int
    document_id: int
    chunk_index: int
    chunk_text: str
    similarity: float  # 相似度分数

    class Config:
        from_attributes = True
