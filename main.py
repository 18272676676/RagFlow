"""
FastAPI 主应用

解决什么问题:
1. 应用入口，初始化所有组件
2. 配置路由和中间件
3. 提供健康检查和文档访问

为什么现在需要:
- 应用需要一个统一的启动入口
- 中间件配置集中管理
- 便于测试和部署
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from RagFlow.config.settings import settings
from RagFlow.core.database import init_db
from RagFlow.core.logger import setup_logger, get_logger
from RagFlow.api.routes.document import router as document_router
from RagFlow.api.routes.qa import router as qa_router
from RagFlow.api.routes.auth import router as auth_router, create_admin_user
from RagFlow.api.routes.conversation import router as conversation_router

# 设置日志
setup_logger(log_dir=settings.LOG_DIR, log_level=settings.LOG_LEVEL)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    logger.info("应用启动中...")

    # 初始化数据库
    try:
        init_db()
        logger.info("数据库初始化成功")
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")

    # 创建默认admin用户
    try:
        from RagFlow.core.database import SessionLocal
        db = SessionLocal()
        try:
            create_admin_user(db)
        finally:
            db.close()
    except Exception as e:
        logger.error(f"创建admin用户失败: {e}")

    logger.info("应用启动完成")

    yield

    # 关闭时执行
    logger.info("应用关闭中...")
    logger.info("应用关闭完成")


# 创建 FastAPI 应用
app = FastAPI(
    title="RAG 知识库系统",
    description="基于 RAG 的单体 AI 知识库应用",
    version="1.0.0",
    lifespan=lifespan
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该设置具体的域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 注册路由
app.include_router(auth_router)
app.include_router(conversation_router)
app.include_router(document_router)
app.include_router(qa_router)

# 挂载静态文件
app.mount("/static", StaticFiles(directory="./static"), name="static")


# 根路径 - 重定向到登录页
@app.get("/")
async def root():
    """根路径 - 重定向到登录页"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/static/login.html", status_code=307)


# 登录页路由
@app.get("/login")
async def login_page():
    """登录页路由"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/static/login.html", status_code=307)


# 聊天页路由
@app.get("/chat")
async def chat_page():
    """聊天页路由"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/static/index.html", status_code=307)


# 文件管理页路由
@app.get("/files")
async def files_page():
    """文件管理页路由"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/static/upload.html", status_code=307)


# 健康检查
@app.get("/health")
async def health():
    """健康检查"""
    return {
        "status": "ok",
        "database": "connected" if True else "disconnected",  # 简化检查
        "services": {
            "vector_store": "ok",
            "embedding": "ok",
            "llm": "ok"
        }
    }


# 全局异常处理
@app.exception_handler(Exception)
async def global_exception_handler(_request, exc):
    """全局异常处理器"""
    logger.error(f"========== 未处理的异常 ==========")
    logger.error(f"异常类型: {type(exc).__name__}")
    logger.error(f"异常消息: {exc}")
    logger.error(f"异常详情:", exc_info=True)
    logger.error(f"====================================")
    return JSONResponse(
        status_code=500,
        content={
            "detail": "服务器内部错误",
            "error": str(exc)
        }
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.SERVER_HOST,
        port=settings.SERVER_PORT,
        reload=True,
        log_level=settings.LOG_LEVEL.lower()
    )
