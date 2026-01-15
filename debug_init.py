"""
调试数据库初始化脚本
"""

import sys
import traceback
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = str(Path(__file__).parent.parent)
print(f"Project root: {project_root}")
sys.path.insert(0, project_root)
print(f"Python path added: {project_root}")
print(f"sys.path[0]: {sys.path[0]}")

print("\n=== Step 1: Importing settings ===")
try:
    from RagFlow.config.settings import settings
    print(f"Settings imported successfully")
    print(f"DATABASE_URL: {settings.DATABASE_URL}")
    print(f"LOG_DIR: {settings.LOG_DIR}")
except Exception as e:
    print(f"ERROR importing settings: {e}")
    traceback.print_exc()
    sys.exit(1)

print("\n=== Step 2: Importing logger ===")
try:
    from RagFlow.core.logger import setup_logger, get_logger
    print("Logger imported successfully")
except Exception as e:
    print(f"ERROR importing logger: {e}")
    traceback.print_exc()
    sys.exit(1)

print("\n=== Step 3: Setting up logger ===")
try:
    setup_logger(log_dir=settings.LOG_DIR, log_level=settings.LOG_LEVEL)
    logger = get_logger(__name__)
    print("Logger setup completed")
except Exception as e:
    print(f"ERROR setting up logger: {e}")
    traceback.print_exc()
    sys.exit(1)

print("\n=== Step 4: Importing database ===")
try:
    from RagFlow.core.database import engine, Base, get_db_session
    print(f"Database imported successfully")
    print(f"Engine URL: {engine.url}")
except Exception as e:
    print(f"ERROR importing database: {e}")
    traceback.print_exc()
    sys.exit(1)

print("\n=== Step 5: Testing database connection ===")
try:
    from sqlalchemy import text
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        print(f"Database connection successful: {result.fetchone()}")
except Exception as e:
    print(f"ERROR connecting to database: {e}")
    traceback.print_exc()
    sys.exit(1)

print("\n=== Step 6: Importing models ===")
try:
    from RagFlow.models.db_models import Document, Chunk, QALog
    print(f"Models imported: Document, Chunk, QALog")
except Exception as e:
    print(f"ERROR importing models: {e}")
    traceback.print_exc()
    sys.exit(1)

print("\n=== Step 7: Creating tables ===")
try:
    print("Starting to create tables...")
    Base.metadata.create_all(bind=engine)
    print("Tables created successfully")

    print("\nCreated tables:")
    for table_name in Base.metadata.tables.keys():
        print(f"  - {table_name}")
except Exception as e:
    print(f"ERROR creating tables: {e}")
    traceback.print_exc()
    sys.exit(1)

print("\n=== All steps completed successfully! ===")
