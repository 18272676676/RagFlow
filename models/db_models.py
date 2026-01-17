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

from sqlalchemy import Column, Integer, String, Text, DateTime, Float, Index, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from RagFlow.core.database import Base
from datetime import datetime


class User(Base):
    """用户表"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, comment="用户 ID")
    username = Column(String(50), unique=True, nullable=False, comment="用户名")
    hashed_password = Column(String(255), nullable=False, comment="加密密码")
    is_active = Column(Integer, default=1, comment="是否激活: 0-否, 1-是")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    # 关系
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="user", cascade="all, delete-orphan")
    knowledge_bases = relationship("KnowledgeBase", back_populates="user", cascade="all, delete-orphan")

    # 添加索引
    __table_args__ = (
        Index('idx_username', 'username'),
    )


class KnowledgeBase(Base):
    """知识库表"""
    __tablename__ = "knowledge_bases"

    id = Column(Integer, primary_key=True, index=True, comment="知识库 ID")
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="所属用户 ID")
    name = Column(String(100), nullable=False, comment="知识库名称")
    description = Column(Text, comment="知识库描述")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    # 关系
    user = relationship("User", back_populates="knowledge_bases")
    documents = relationship("Document", back_populates="knowledge_base", cascade="all, delete-orphan")

    # 添加索引
    __table_args__ = (
        Index('idx_user_id', 'user_id'),
        Index('idx_name', 'name'),
    )


class Conversation(Base):
    """对话会话表"""
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True, comment="会话 ID")
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="用户 ID")
    knowledge_base_id = Column(Integer, ForeignKey("knowledge_bases.id"), nullable=True, comment="关联的知识库 ID")
    title = Column(String(200), nullable=False, default="新对话", comment="会话标题")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    # 关系
    user = relationship("User", back_populates="conversations")
    knowledge_base = relationship("KnowledgeBase", backref="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
    qa_logs = relationship("QALog", back_populates="conversation", cascade="all, delete-orphan")

    # 添加索引
    __table_args__ = (
        Index('idx_user_id', 'user_id'),
        Index('idx_created_at', 'created_at'),
    )


class Message(Base):
    """会话消息表"""
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True, comment="消息 ID")
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False, comment="会话 ID")
    role = Column(String(20), nullable=False, comment="角色: user/assistant")
    content = Column(Text, nullable=False, comment="消息内容")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")

    # 关系
    conversation = relationship("Conversation", back_populates="messages")

    # 添加索引
    __table_args__ = (
        Index('idx_conversation_id', 'conversation_id'),
        Index('idx_created_at', 'created_at'),
    )


class Document(Base):
    """文档表"""
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True, comment="文档 ID")
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, comment="上传用户 ID (可为空)")
    knowledge_base_id = Column(Integer, ForeignKey("knowledge_bases.id"), nullable=True, comment="所属知识库 ID")
    file_name = Column(String(255), nullable=False, comment="文件名")
    file_path = Column(String(500), nullable=False, comment="文件存储路径")
    file_size = Column(Integer, nullable=False, comment="文件大小（字节）")
    file_type = Column(String(50), nullable=False, comment="文件类型")
    status = Column(String(20), nullable=False, default="pending", comment="处理状态")
    chunk_count = Column(Integer, default=0, comment="切片数量")
    error_message = Column(Text, comment="错误信息")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    # 关系
    user = relationship("User", back_populates="documents")
    knowledge_base = relationship("KnowledgeBase", back_populates="documents")
    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")

    # 添加索引
    __table_args__ = (
        Index('idx_file_name', 'file_name'),
        Index('idx_status', 'status'),
        Index('idx_knowledge_base_id', 'knowledge_base_id'),
        Index('idx_created_at', 'created_at'),
    )


class Chunk(Base):
    """文档切片表"""
    __tablename__ = "chunks"

    id = Column(Integer, primary_key=True, index=True, comment="切片 ID")
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False, comment="所属文档 ID")
    chunk_index = Column(Integer, nullable=False, comment="切片索引（从0开始）")
    chunk_text = Column(Text, nullable=False, comment="切片文本内容")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")

    # 关系
    document = relationship("Document", back_populates="chunks")

    # 添加索引
    __table_args__ = (
        Index('idx_document_id', 'document_id'),
        Index('idx_chunk_index', 'chunk_index'),
    )


class QALog(Base):
    """问答日志表"""
    __tablename__ = "qa_logs"

    id = Column(Integer, primary_key=True, index=True, comment="日志 ID")
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=True, comment="会话 ID")
    request_id = Column(String(100), nullable=False, comment="请求 ID")
    question = Column(Text, nullable=False, comment="用户问题")
    answer = Column(Text, comment="模型回答")
    source_document_ids = Column(Text, comment="来源文档 ID 列表（JSON 格式）")
    prompt_tokens = Column(Integer, comment="提示词 token 数")
    completion_tokens = Column(Integer, comment="完成 token 数")
    total_tokens = Column(Integer, comment="总 token 数")
    error_message = Column(Text, comment="错误信息")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")

    # 关系
    conversation = relationship("Conversation", back_populates="qa_logs")

    # 添加索引
    __table_args__ = (
        Index('idx_request_id', 'request_id'),
        Index('idx_conversation_id', 'conversation_id'),
        Index('idx_created_at', 'created_at'),
    )
