"""
数据库 ORM 模型

解决什么问题:
1. 定义数据库表结构，映射到 Python 类
2. 提供类型安全的数据库操作
3. 支持数据库迁移

为什么现在需要:
- ORM 模型是数据库操作的基石
- 类型安全减少运行时错误
- 便于数据库版本管理和迁移
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Float, Index
from sqlalchemy.sql import func
from RagFlow.core.database import Base
from datetime import datetime


class Document(Base):
    """文档表"""
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True, comment="文档 ID")
    file_name = Column(String(255), nullable=False, comment="文件名")
    file_path = Column(String(500), nullable=False, comment="文件存储路径")
    file_size = Column(Integer, nullable=False, comment="文件大小（字节）")
    file_type = Column(String(50), nullable=False, comment="文件类型")
    status = Column(String(20), nullable=False, default="pending", comment="处理状态")
    chunk_count = Column(Integer, default=0, comment="切片数量")
    error_message = Column(Text, comment="错误信息")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    # 添加索引
    __table_args__ = (
        Index('idx_file_name', 'file_name'),
        Index('idx_status', 'status'),
        Index('idx_created_at', 'created_at'),
    )


class Chunk(Base):
    """文档切片表"""
    __tablename__ = "chunks"

    id = Column(Integer, primary_key=True, index=True, comment="切片 ID")
    document_id = Column(Integer, nullable=False, comment="所属文档 ID")
    chunk_index = Column(Integer, nullable=False, comment="切片序号")
    chunk_text = Column(Text, nullable=False, comment="切片文本内容")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")

    # 添加索引
    __table_args__ = (
        Index('idx_document_id', 'document_id'),
        Index('idx_chunk_index', 'chunk_index'),
    )


class QALog(Base):
    """问答日志表"""
    __tablename__ = "qa_logs"

    id = Column(Integer, primary_key=True, index=True, comment="日志 ID")
    request_id = Column(String(100), nullable=False, comment="请求 ID")
    question = Column(Text, nullable=False, comment="用户问题")
    answer = Column(Text, comment="模型回答")
    source_document_ids = Column(Text, comment="来源文档 ID 列表（JSON 格式）")
    prompt_tokens = Column(Integer, comment="提示词 token 数")
    completion_tokens = Column(Integer, comment="完成 token 数")
    total_tokens = Column(Integer, comment="总 token 数")
    error_message = Column(Text, comment="错误信息")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")

    # 添加索引
    __table_args__ = (
        Index('idx_request_id', 'request_id'),
        Index('idx_created_at', 'created_at'),
    )
