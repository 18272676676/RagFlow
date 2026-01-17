"""
数据库连接模块

解决什么问题:
1. 提供统一的数据库连接管理
2. 支持连接池配置，提高性能
3. 提供数据库会话管理，避免连接泄漏

为什么现在需要:
- 数据库连接是应用的基础设施
- 需要连接池来管理数据库连接资源
- 统一会话管理保证事务的一致性
"""

from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from contextlib import contextmanager
from typing import Generator
from RagFlow.config.settings import settings

# 创建数据库引擎
engine: Engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,  # 连接池预检测，避免连接失效
    pool_size=10,  # 连接池大小
    max_overflow=20,  # 最大溢出连接数
    pool_recycle=3600,  # 连接回收时间（秒）
    echo=False,  # 是否输出 SQL 日志（调试时启用）
    connect_args={
        "charset": "utf8mb4",
    }
)

# 在引擎启动时设置全局时区
from sqlalchemy import event

@event.listens_for(engine, "connect")
def set_time_zone_on_connect(dbapi_conn, connection_record):
    """每次建立数据库连接时设置时区"""
    cursor = dbapi_conn.cursor()
    try:
        cursor.execute(f"SET time_zone = '{settings.DB_TIMEZONE}'")
        cursor.execute("SET NAMES utf8mb4")
    finally:
        cursor.close()

# 创建 Session 工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建基类，所有 ORM 模型继承自此类
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    获取数据库会话（依赖注入）

    使用方式:
        @app.get("/api/documents")
        def list_documents(db: Session = Depends(get_db)):
            # 使用 db 进行数据库操作
            pass

    Yields:
        Session: 数据库会话对象
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """
    获取数据库会话（上下文管理器）

    使用方式:
        with get_db_session() as db:
            # 使用 db 进行数据库操作
            pass

    Yields:
        Session: 数据库会话对象
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db():
    """
    初始化数据库

    创建所有定义的表结构
    """
    from RagFlow.models.db_models import User, Conversation, Message, Document, Chunk, QALog

    # 创建所有表
    Base.metadata.create_all(bind=engine)
