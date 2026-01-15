"""
文档管理 API 路由

解决什么问题:
1. 提供文档上传、查询、删除的 HTTP 接口
2. 处理文件上传和存储
3. 触发知识构建流程

为什么现在需要:
- 需要通过 HTTP 接口与前端交互
- 文件上传是知识构建的入口
- API 层隔离业务逻辑，提高可测试性
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List
from pathlib import Path
import uuid
import aiofiles

from RagFlow.core.database import get_db
from RagFlow.core.logger import get_logger, set_request_id
from RagFlow.models.db_models import Document
from RagFlow.models.document import DocumentResponse
from RagFlow.services.knowledge_builder import KnowledgeBuilder
from RagFlow.config.settings import settings

logger = get_logger(__name__)

# 创建路由器
router = APIRouter(prefix="/api/documents", tags=["文档管理"])

# 初始化知识构建器
knowledge_builder = KnowledgeBuilder()


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    上传文档接口

    文件上传后触发知识构建流程，包括：
    1. 解析文档内容
    2. 分块处理
    3. 计算 Embedding
    4. 存储到向量库

    支持的文件格式: .txt, .md, .pdf, .docx
    """
    set_request_id()
    logger.info(f"开始上传文档: {file.filename}")

    # 1. 验证文件类型
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")

    # 获取文件扩展名
    file_ext = Path(file.filename).suffix.lower()

    # 检查文档解析器是否支持该文件类型
    from RagFlow.services.document_parser import DocumentParserFactory
    if not DocumentParserFactory.is_supported(file.filename):
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型: {file.filename}，仅支持 {', '.join(DocumentParserFactory.get_supported_extensions())}"
        )

    # 2. 检查文件大小
    content = await file.read()
    if len(content) > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"文件过大，最大支持 {settings.MAX_FILE_SIZE // 1024 // 1024}MB"
        )

    # 3. 保存文件
    file_id = uuid.uuid4().hex
    file_path = Path(knowledge_builder.upload_dir) / f"{file_id}{file_ext}"

    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)

    # 4. 创建文档记录
    document = Document(
        file_name=file.filename,
        file_path=str(file_path),
        file_size=len(content),
        file_type=file_ext[1:],
        status="pending"
    )

    db.add(document)
    db.commit()
    db.refresh(document)

    # 5. 异步触发知识构建
    import asyncio
    asyncio.create_task(knowledge_builder.build_knowledge(
        document_id=document.id,
        file_path=str(file_path),
        file_name=file.filename,
        db=db
    ))

    logger.info(f"文档上传成功，document_id: {document.id}")
    return document


@router.get("", response_model=List[DocumentResponse])
async def list_documents(
    status: str = None,
    skip: int = 0,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """
    查询文档列表

    Args:
        status: 文档状态筛选
        skip: 跳过数量
        limit: 返回数量
    """
    set_request_id()

    query = db.query(Document)

    if status:
        query = query.filter(Document.status == status)

    documents = query.order_by(Document.created_at.desc()).offset(skip).limit(limit).all()
    logger.info(f"查询文档列表，数量: {len(documents)}")

    return documents


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: int,
    db: Session = Depends(get_db)
):
    """查询单个文档详情"""
    set_request_id()

    document = db.query(Document).filter(Document.id == document_id).first()

    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")

    return document


@router.delete("/{document_id}")
async def delete_document(
    document_id: int,
    db: Session = Depends(get_db)
):
    """
    删除文档

    删除文档文件、数据库记录和向量库索引
    """
    set_request_id()
    logger.info(f"开始删除文档: {document_id}")

    # 检查文档是否存在
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")

    # 删除文档及相关知识
    success = knowledge_builder.delete_document(document_id, db)

    if success:
        return JSONResponse(
            content={"message": "文档删除成功"},
            status_code=200
        )
    else:
        raise HTTPException(status_code=500, detail="文档删除失败")


@router.get("/{document_id}/chunks")
async def get_document_chunks(
    document_id: int,
    db: Session = Depends(get_db)
):
    """
    查询文档的所有切片

    用于调试和查看分块结果
    """
    set_request_id()

    # 检查文档是否存在
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")

    # 查询所有切片
    from RagFlow.models.db_models import Chunk
    chunks = db.query(Chunk).filter(Chunk.document_id == document_id).order_by(Chunk.chunk_index).all()

    chunk_list = [
        {
            "chunk_index": c.chunk_index,
            "chunk_text": c.chunk_text[:200] + "..." if len(c.chunk_text) > 200 else c.chunk_text,
            "created_at": c.created_at
        }
        for c in chunks
    ]

    return {
        "document_id": document_id,
        "file_name": document.file_name,
        "chunk_count": len(chunks),
        "chunks": chunk_list
    }
