"""
配置管理模块

解决什么问题:
1. 集中管理所有配置项，避免配置分散在代码中
2. 通过环境变量管理不同环境（开发/测试/生产）的配置差异
3. 提供类型安全的配置访问方式

为什么现在需要:
- 配置是应用的基础，需要在代码运行前就确定
- 避免硬编码配置，提高可移植性和安全性
- 便于部署时的配置切换
"""

from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    """应用配置类"""

    # ==================== 数据库配置 ====================
    DB_HOST: str = "117.72.188.95"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = "Weida&6676"
    DB_NAME: str = "rag_knowledge_base"
    DB_TIMEZONE: str = "+08:00"  # 数据库时区（北京时间 UTC+8）

    # ==================== DeepSeek API 配置 ====================
    DEEPSEEK_API_BASE: str = "https://api.deepseek.com/v1/chat/completions"
    DEEPSEEK_API_KEY: str = "sk-4b0f7c63d4cb47aab8ac30a7474e559e"
    DEEPSEEK_MODEL: str = "deepseek-chat"

    # ==================== 向量库配置 ====================
    VECTOR_DB_TYPE: str = "faiss"  # faiss, milvus, chroma
    FAISS_INDEX_PATH: str = "./data/vector_store/faiss_index"
    EMBEDDING_MODEL: str = "shibing624/text2vec-base-chinese"
    EMBEDDING_CACHE_DIR: str = r"D:\codeing\python\ANMS\models\embeddings"  # Embedding 模型缓存目录

    # ==================== 文档处理配置 ====================
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 50
    MAX_FILE_SIZE: int = 10485760  # 10MB

    # ==================== RAG 配置 ====================
    TOP_K: int = 5
    TEMPERATURE: float = 0.7
    MAX_TOKENS: int = 2000
    SIMILARITY_THRESHOLD: float = 0.3  # 相似度阈值，低于此值认为知识库中没有相关内容

    # ==================== 日志配置 ====================
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "./logs"

    # ==================== 服务配置 ====================
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8000

    # ==================== MinIO 配置 ====================
    MINIO_ENDPOINT: str = "http://117.72.188.95:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin123"
    MINIO_BUCKET_NAME: str = "rag-documents"
    MINIO_SECURE: bool = False
    USE_MINIO: bool = True  # 是否使用MinIO存储

    # ==================== 认证配置 ====================
    SECRET_KEY: str = "your-secret-key-change-in-production-2024"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7天

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

    @property
    def DATABASE_URL(self) -> str:
        """构建数据库连接 URL"""
        from urllib.parse import quote_plus
        # 对密码中的特殊字符进行 URL 编码
        encoded_password = quote_plus(self.DB_PASSWORD)
        return f"mysql+pymysql://{self.DB_USER}:{encoded_password}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"


# 全局配置实例
settings = Settings()
