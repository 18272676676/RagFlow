"""
数据库初始化脚本

解决什么问题:
1. 创建数据库和表结构
2. 提供数据库迁移的基础
3. 独立的初始化脚本，便于部署

为什么现在需要:
- 数据库初始化是部署的第一步
- 需要明确的表结构定义
- 便于数据库版本管理
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = str(Path(__file__).parent.parent)
sys.path.insert(0, project_root)

# 验证路径
print(f"Project root: {project_root}")
print(f"Python path[0]: {sys.path[0]}")

# 尝试导入
try:
    from RagFlow.core.database import engine, Base, get_db_session
    print(f"Database module imported: {engine.url}")
except ImportError as e:
    print(f"Import Error: {e}")
    print(f"Available paths: {sys.path}")
    sys.exit(1)

from RagFlow.models.db_models import Document, Chunk, QALog
from RagFlow.config.settings import settings
from RagFlow.core.logger import setup_logger, get_logger

# 设置日志
try:
    setup_logger(log_dir=settings.LOG_DIR, log_level=settings.LOG_LEVEL)
    logger = get_logger(__name__)
    print("Logger setup completed")
except Exception as e:
    print(f"Logger setup error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)


def create_tables():
    """创建所有表"""
    print("开始创建数据库表...")
    logger.info("开始创建数据库表...")

    try:
        # 创建所有表
        Base.metadata.create_all(bind=engine)
        print("数据库表创建成功")
        logger.info("数据库表创建成功")

        # 显示表信息
        print("已创建的表:")
        logger.info("已创建的表:")
        for table_name in Base.metadata.tables.keys():
            print(f"  - {table_name}")
            logger.info(f"  - {table_name}")

    except Exception as e:
        print(f"创建数据库表失败: {e}")
        logger.error(f"创建数据库表失败: {e}")
        raise


def drop_tables():
    """删除所有表（谨慎使用）"""
    logger.warning("开始删除数据库表...")

    try:
        Base.metadata.drop_all(bind=engine)
        logger.warning("数据库表删除成功")

    except Exception as e:
        logger.error(f"删除数据库表失败: {e}")
        raise


def reset_database():
    """重置数据库（删除并重新创建）"""
    logger.warning("开始重置数据库...")

    try:
        drop_tables()
        create_tables()
        logger.info("数据库重置成功")

    except Exception as e:
        logger.error(f"重置数据库失败: {e}")
        raise


def show_tables():
    """显示所有表结构"""
    logger.info("查看数据库表结构...")

    try:
        with get_db_session() as db:
            # 查看 documents 表
            result = db.execute("DESCRIBE documents")
            logger.info("documents 表结构:")
            for row in result:
                logger.info(f"  {row}")

            # 查看 chunks 表
            result = db.execute("DESCRIBE chunks")
            logger.info("chunks 表结构:")
            for row in result:
                logger.info(f"  {row}")

            # 查看 qa_logs 表
            result = db.execute("DESCRIBE qa_logs")
            logger.info("qa_logs 表结构:")
            for row in result:
                logger.info(f"  {row}")

    except Exception as e:
        logger.error(f"查看表结构失败: {e}")
        raise


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="数据库初始化脚本")
    parser.add_argument("--create", action="store_true", help="创建表")
    parser.add_argument("--drop", action="store_true", help="删除表")
    parser.add_argument("--reset", action="store_true", help="重置数据库")
    parser.add_argument("--show", action="store_true", help="显示表结构")

    args = parser.parse_args()

    if args.drop:
        drop_tables()
    elif args.reset:
        reset_database()
    elif args.show:
        show_tables()
    else:
        create_tables()
