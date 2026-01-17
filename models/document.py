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
from RagFlow.models.db_models import Document


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
    status_text: Optional[str] = None  # 状态中文描述
    chunk_count: int = 0
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    formatted_size: Optional[str] = None  # 格式化的文件大小
    formatted_created_at: Optional[str] = None  # 格式化的创建时间

    class Config:
        from_attributes = True


def format_document_response(document: Document) -> dict:
    """格式化文档响应，添加中文状态和格式化时间"""
    status_map = {
        "pending": "待处理",
        "processing": "处理中",
        "completed": "已完成（已向量化）",
        "failed": "处理失败"
    }

    # 格式化文件大小
    if document.file_size < 1024:
        formatted_size = f"{document.file_size} B"
    elif document.file_size < 1024 * 1024:
        formatted_size = f"{document.file_size / 1024:.2f} KB"
    else:
        formatted_size = f"{document.file_size / (1024 * 1024):.2f} MB"

    # 格式化创建时间（北京时间）
    from datetime import timedelta
    beijing_time = document.created_at + timedelta(hours=8)
    formatted_created_at = beijing_time.strftime("%Y-%m-%d %H:%M:%S")

    return {
        "id": document.id,
        "file_name": document.file_name,
        "file_path": document.file_path,
        "file_size": document.file_size,
        "file_type": document.file_type,
        "status": document.status,
        "status_text": status_map.get(document.status, "未知状态"),
        "chunk_count": document.chunk_count,
        "error_message": document.error_message,
        "created_at": document.created_at,
        "updated_at": document.updated_at,
        "formatted_size": formatted_size,
        "formatted_created_at": formatted_created_at
    }


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
