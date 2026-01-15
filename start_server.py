"""
服务启动脚本

解决什么问题:
1. 提供便捷的服务启动方式
2. 统一配置管理
3. 支持 Docker 部署

为什么现在需要:
- 服务启动需要统一入口
- 环境配置需要集中管理
- 便于运维和部署
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import uvicorn
from RagFlow.config.settings import settings
from RagFlow.core.logger import setup_logger, get_logger

# 设置日志
setup_logger(log_dir=settings.LOG_DIR, log_level=settings.LOG_LEVEL)
logger = get_logger(__name__)


def main():
    """启动服务"""
    logger.info("=" * 50)
    logger.info("RAG 知识库系统启动中...")
    logger.info("=" * 50)
    logger.info(f"服务地址: http://{settings.SERVER_HOST}:{settings.SERVER_PORT}")
    logger.info(f"API 文档: http://{settings.SERVER_HOST}:{settings.SERVER_PORT}/docs")
    logger.info("=" * 50)

    # 启动服务
    uvicorn.run(
        "main:app",
        host=settings.SERVER_HOST,
        port=settings.SERVER_PORT,
        reload=False,  # 生产环境不使用 reload
        workers=1,  # 单体应用使用单进程
        log_level=settings.LOG_LEVEL.lower(),
        access_log=True
    )


if __name__ == "__main__":
    main()
