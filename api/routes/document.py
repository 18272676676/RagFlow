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
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session
from typing import List
from pathlib import Path
import uuid
import io
from urllib.parse import quote
import mimetypes

from RagFlow.core.database import get_db
from RagFlow.core.logger import get_logger, set_request_id
from RagFlow.core.auth import get_current_active_user
from RagFlow.models.db_models import Document, User, Chunk
from RagFlow.models.document import DocumentResponse
from RagFlow.services.knowledge_builder import KnowledgeBuilder
from RagFlow.services.storage_service import get_storage_service
from RagFlow.config.settings import settings

logger = get_logger(__name__)

# 创建路由器
router = APIRouter(prefix="/api/documents", tags=["文档管理"])

# 延迟初始化知识构建器
knowledge_builder = None

def get_knowledge_builder():
    """获取知识构建器实例（延迟加载）"""
    global knowledge_builder
    if knowledge_builder is None:
        logger.info("初始化知识构建器...")
        knowledge_builder = KnowledgeBuilder()
        logger.info("知识构建器初始化成功")
    return knowledge_builder


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
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
    logger.info(f"========== 开始上传文档 ==========")
    logger.info(f"文件名: {file.filename}")
    logger.info(f"文件大小: {file.size if hasattr(file, 'size') else '未知'}")
    logger.info(f"用户ID: {current_user.id}")
    logger.info(f"用户名: {current_user.username}")
    logger.info(f"Content-Type: {file.content_type if hasattr(file, 'content_type') else '未知'}")

    # 1. 验证文件类型
    if not file.filename:
        logger.error("文件名不能为空")
        raise HTTPException(status_code=400, detail="文件名不能为空")

    logger.info(f"验证文件名成功")

    # 获取文件扩展名
    file_ext = Path(file.filename).suffix.lower()
    logger.info(f"文件扩展名: {file_ext}")

    # 检查文档解析器是否支持该文件类型
    from RagFlow.services.document_parser import DocumentParserFactory
    if not DocumentParserFactory.is_supported(file.filename):
        logger.error(f"不支持的文件类型: {file.filename}")
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型: {file.filename}，仅支持 {', '.join(DocumentParserFactory.get_supported_extensions())}"
        )

    logger.info(f"文件类型验证通过")

    # 2. 读取文件内容
    try:
        content = await file.read()
        logger.info(f"读取文件内容成功，大小: {len(content)} bytes")
    except Exception as e:
        logger.error(f"读取文件内容失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"读取文件失败: {str(e)}")

    if len(content) > settings.MAX_FILE_SIZE:
        logger.error(f"文件过大: {len(content)} bytes")
        raise HTTPException(
            status_code=400,
            detail=f"文件过大，最大支持 {settings.MAX_FILE_SIZE // 1024 // 1024}MB"
        )

    logger.info(f"文件大小验证通过")

    # 3. 创建文档记录
    file_id = uuid.uuid4().hex
    storage_path = f"{current_user.id}/{file_id}{file_ext}"

    logger.info(f"生成文档记录: file_id={file_id}, storage_path={storage_path}")

    document = Document(
        user_id=current_user.id,
        file_name=file.filename,
        file_path=storage_path,
        file_size=len(content),
        file_type=file_ext[1:],
        status="pending"
    )

    db.add(document)
    try:
        db.commit()
        db.refresh(document)
        logger.info(f"数据库记录创建成功，document_id={document.id}")
    except Exception as e:
        logger.error(f"数据库提交失败: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"数据库操作失败: {str(e)}")

    # 4. 异步触发知识构建 - 直接使用内存中的content，无需从存储下载
    import asyncio

    logger.info(f"准备触发知识构建任务")
    kb = get_knowledge_builder()
    asyncio.create_task(kb.build_knowledge_from_content(
        document_id=document.id,
        file_content=content,
        file_name=file.filename,
        file_ext=file_ext,
        storage_path=storage_path,
        db=db
    ))
    logger.info(f"知识构建任务已异步触发")

    # 5. 异步上传文件到存储（不阻塞响应）
    async def upload_to_storage():
        storage_service = get_storage_service()
        try:
            logger.info(f"[存储任务] 准备上传文件到存储")
            logger.info(f"[存储任务] storage_path={storage_path}, file_name={file.filename}, size={len(content)}")
            result = await storage_service.upload_file(storage_path, file.filename, content)
            logger.info(f"[存储任务] 文件上传到存储成功: {storage_path}, 结果: {result}")
        except Exception as e:
            logger.error(f"[存储任务] 文件上传到存储失败: {e}", exc_info=True)

    asyncio.create_task(upload_to_storage())
    logger.info(f"存储上传任务已异步触发")

    logger.info(f"========== 文档上传接口返回成功 ==========")
    logger.info(f"document_id={document.id}")
    logger.info(f"===========================================")

    # 返回格式化的文档信息
    from RagFlow.models.document import format_document_response
    return format_document_response(document)


@router.get("")
async def list_documents(
    status: str = None,
    skip: int = 0,
    limit: int = 10,
    current_user: User = Depends(get_current_active_user),
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

    query = db.query(Document).filter(Document.user_id == current_user.id)

    if status:
        query = query.filter(Document.status == status)

    documents = query.order_by(Document.created_at.desc()).offset(skip).limit(limit).all()
    logger.info(f"查询文档列表，数量: {len(documents)}")

    # 转换为响应格式并添加格式化字段，动态计算每个文档的实际切片数量
    from RagFlow.models.document import format_document_response
    result = []
    for doc in documents:
        actual_chunk_count = db.query(Chunk).filter(Chunk.document_id == doc.id).count()
        result.append(format_document_response(doc, actual_chunk_count=actual_chunk_count))

    return result


@router.get("/{document_id}")
async def get_document(
    document_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """查询单个文档详情"""
    set_request_id()

    document = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id
    ).first()

    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")

    # 动态计算实际切片数量，确保数据一致性
    actual_chunk_count = db.query(Chunk).filter(Chunk.document_id == document_id).count()

    # 返回格式化的文档信息
    from RagFlow.models.document import format_document_response
    return format_document_response(document, actual_chunk_count=actual_chunk_count)


@router.get("/{document_id}/download")
async def download_document(
    document_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """下载文档文件"""
    set_request_id()

    document = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id
    ).first()

    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")

    storage_service = get_storage_service()
    try:
        content = await storage_service.download_file(document.file_path)

        # 根据文件扩展名确定MIME类型
        mime_type, _ = mimetypes.guess_type(document.file_name)
        if mime_type is None:
            mime_type = "application/octet-stream"

        # 对中文文件名进行URL编码
        encoded_filename = quote(document.file_name, safe='')

        # 只使用filename*，避免latin-1编码问题
        return StreamingResponse(
            io.BytesIO(content),
            media_type=mime_type,
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
            }
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="文件不存在")


@router.delete("/{document_id}")
async def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    删除文档

    删除文档文件、数据库记录和向量库索引
    """
    set_request_id()
    logger.info(f"开始删除文档: {document_id}")

    # 检查文档是否存在
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id
    ).first()

    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")

    # 删除存储文件
    storage_service = get_storage_service()
    await storage_service.delete_file(document.file_path)

    # 删除文档及相关知识
    kb = get_knowledge_builder()
    success = kb.delete_document(document_id, db)

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
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    查询文档的所有切片

    用于调试和查看分块结果
    """
    set_request_id()

    # 检查文档是否存在
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id
    ).first()

    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")

    # 查询所有切片
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
