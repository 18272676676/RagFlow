"""
测试导入脚本
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = str(Path(__file__).parent.parent)
print(f"Project root: {project_root}")
sys.path.insert(0, project_root)

try:
    print("Importing RagFlow.config.settings...")
    from RagFlow.config.settings import settings
    print(f"DATABASE_URL: {settings.DATABASE_URL}")
    print(f"LOG_DIR: {settings.LOG_DIR}")
except Exception as e:
    print(f"Error importing settings: {e}")
    import traceback
    traceback.print_exc()

try:
    print("\nImporting RagFlow.core.logger...")
    from RagFlow.core.logger import setup_logger, get_logger
    print("Logger imported successfully")
except Exception as e:
    print(f"Error importing logger: {e}")
    import traceback
    traceback.print_exc()

try:
    print("\nImporting RagFlow.core.database...")
    from RagFlow.core.database import engine, Base
    print(f"Engine: {engine}")
    print(f"Engine URL: {engine.url}")
except Exception as e:
    print(f"Error importing database: {e}")
    import traceback
    traceback.print_exc()

try:
    print("\nImporting RagFlow.models.db_models...")
    from RagFlow.models.db_models import Document, Chunk, QALog
    print(f"Models imported: Document, Chunk, QALog")
except Exception as e:
    print(f"Error importing models: {e}")
    import traceback
    traceback.print_exc()

print("\nAll imports completed!")
