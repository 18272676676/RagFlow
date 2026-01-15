# 架构设计文档

## 系统概述

本项目是一个基于 RAG（Retrieval-Augmented Generation）的单体 AI 知识库应用，采用清晰的分层架构设计。

## 分层架构

```
┌─────────────────────────────────────────────────────────┐
│                        API 层                              │
│                    (HTTP 接口)                             │
├─────────────────────────────────────────────────────────┤
│                      业务服务层                            │
│  ┌──────────┬──────────┬──────────┬──────────┬────────┐  │
│  │ 文档管理 │ 问答服务 │ 检索模块 │ 知识构建 │ LLM    │  │
│  └──────────┴──────────┴──────────┴──────────┴────────┘  │
├─────────────────────────────────────────────────────────┤
│                      数据模型层                            │
│           (ORM 模型 + 领域模型)                           │
├─────────────────────────────────────────────────────────┤
│                      核心设施层                            │
│        (数据库连接 | 日志 | 配置管理)                      │
├─────────────────────────────────────────────────────────┤
│                    外部依赖层                              │
│  ┌──────────┬──────────┬──────────┬──────────┐         │
│  │  MySQL   │  FAISS   │ DeepSeek │Embedding │         │
│  └──────────┴──────────┴──────────┴──────────┘         │
└─────────────────────────────────────────────────────────┘
```

## 模块职责

### API 层 (`api/`)

**职责**:
- 提供 HTTP 接口
- 请求参数验证
- 调用业务服务
- 返回响应数据

**模块**:
- `document.py`: 文档上传、查询、删除接口
- `qa.py`: 问答接口、健康检查

**设计原则**:
- API 层不包含业务逻辑
- 统一异常处理
- 明确的请求/响应模型

### 业务服务层 (`services/`)

**职责**:
- 封装业务逻辑
- 协调多个模块协作
- 事务管理

**模块**:
- `document_parser.py`: 文档解析（TXT/MD/PDF/DOCX）
- `chunker.py`: 文档分块（可配置）
- `embedding.py`: Embedding 服务（抽象接口）
- `vector_store.py`: 向量库（抽象接口）
- `knowledge_builder.py`: 知识构建流程编排
- `retriever.py`: 向量检索
- `prompt_builder.py`: Prompt 构建
- `llm.py`: LLM 调用（抽象接口）
- `qa_service.py`: 问答服务编排

**设计原则**:
- 单一职责
- 依赖注入
- 接口抽象

### 数据模型层 (`models/`)

**职责**:
- 定义数据结构
- 数据验证
- ORM 映射

**模块**:
- `db_models.py`: 数据库 ORM 模型
- `document.py`: 文档领域模型
- `qa.py`: 问答领域模型

**设计原则**:
- 领域模型与 ORM 模型分离
- 类型安全
- 数据验证

### 核心设施层 (`core/`, `config/`)

**职责**:
- 提供基础设施
- 配置管理
- 日志记录

**模块**:
- `database.py`: 数据库连接和会话管理
- `logger.py`: 日志系统（request_id 追踪）
- `settings.py`: 配置管理

**设计原则**:
- 集中管理
- 环境变量配置
- 结构化日志

## 数据流

### 知识构建流程

```
┌─────────────┐
│ 用户上传文档 │
└──────┬──────┘
       │
       ▼
┌─────────────────────┐
│  API: /upload       │
│ - 验证文件类型       │
│ - 验证文件大小       │
│ - 保存文件           │
│ - 创建文档记录       │
└──────┬──────────────┘
       │
       ▼
┌────────────────────────────┐
│ KnowledgeBuilder.build      │
│ - 解析文档内容            │
│ - 分块处理               │
│ - 计算 Embedding         │
│ - 存储到向量库            │
│ - 更新数据库状态          │
└────────────────────────────┘
```

### 问答流程

```
┌─────────────┐
│ 用户提问    │
└──────┬──────┘
       │
       ▼
┌─────────────────────┐
│  API: /ask          │
│ - 验证问题           │
│ - 调用问答服务       │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│ QAService.ask                        │
│                                     │
│ ┌──────────────┐                    │
│ │ Retriever    │                    │
│ │ - Embedding  │                    │
│ │ - 向量检索    │                    │
│ └──────┬───────┘                    │
│        │                            │
│        ▼                            │
│ ┌──────────────┐                    │
│ │ PromptBuilder│                    │
│ │ - 构建 Prompt │                    │
│ └──────┬───────┘                    │
│        │                            │
│        ▼                            │
│ ┌──────────────┐                    │
│ │ LLMService   │                    │
│ │ - 调用 LLM   │                    │
│ └──────┬───────┘                    │
│        │                            │
│        ▼                            │
│ 返回答案 + 来源信息                  │
└─────────────────────────────────────┘
```

## 接口抽象

### Embedding 接口

```python
class EmbeddingModel(ABC):
    @abstractmethod
    def embed(self, text: str) -> List[float]:
        pass

    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        pass
```

**实现**:
- `SentenceTransformerEmbedding`

### 向量库接口

```python
class VectorStore(ABC):
    @abstractmethod
    def add_documents(self, documents: List[Dict], embeddings: List[List[float]]) -> None:
        pass

    @abstractmethod
    def search(self, query_embedding: List[float], top_k: int) -> List[SearchResult]:
        pass

    @abstractmethod
    def delete_by_document_id(self, document_id: int) -> None:
        pass

    @abstractmethod
    def clear(self) -> None:
        pass
```

**实现**:
- `FAISSVectorStore`

### LLM 接口

```python
class LLMModel(ABC):
    @abstractmethod
    def chat(self, messages: List[Dict], temperature: float, max_tokens: int) -> LLMResponse:
        pass
```

**实现**:
- `DeepSeekLLM`

## 可扩展性

### 替换 Embedding 模型

```python
# 实现 EmbeddingModel 接口
class CustomEmbedding(EmbeddingModel):
    def embed(self, text: str) -> List[float]:
        # 自定义实现
        pass

# 注入服务
embedding_service = EmbeddingService(CustomEmbedding())
```

### 替换向量库

```python
# 实现 VectorStore 接口
class CustomVectorStore(VectorStore):
    def add_documents(self, documents, embeddings):
        # 自定义实现
        pass

# 使用工厂创建
vector_store = VectorStoreFactory.create_vector_store(
    store_type="custom",
    **kwargs
)
```

### 替换 LLM

```python
# 实现 LLMModel 接口
class CustomLLM(LLMModel):
    def chat(self, messages, temperature, max_tokens):
        # 自定义实现
        pass

# 注入服务
llm_service = LLMService(CustomLLM())
```

## 日志追踪

使用 request_id 进行日志追踪：

```python
# 设置 request_id
set_request_id(request_id)

# 获取 logger
logger = get_logger(__name__)

# 日志会自动包含 request_id
logger.info("处理请求")
```

日志格式：
```
2024-01-10 12:00:00 | INFO     | 123e4567-e89b-12d3-a456-426614174000 | services.qa_service:ask:45 - 开始处理问答请求
```

## 配置管理

所有配置通过环境变量管理：

```python
from config.settings import settings

# 使用配置
db_url = settings.DATABASE_URL
api_key = settings.DEEPSEEK_API_KEY
```

## 部署架构

### Docker 部署

```
┌─────────────────────────────────────────────┐
│               Docker Host                   │
├─────────────────────────────────────────────┤
│  ┌──────────────┐      ┌──────────────┐    │
│  │    App       │──────│    MySQL     │    │
│  │  Container   │      │  Container   │    │
│  └──────────────┘      └──────────────┘    │
│         │                                  │
│         ▼                                  │
│  ┌──────────────┐                          │
│  │  Data Volume │                          │
│  └──────────────┘                          │
└─────────────────────────────────────────────┘
```

### 网络架构

```
Internet
    │
    ▼
┌──────────────┐
│  Nginx (可选) │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  FastAPI App │ (Port 8000)
└──────┬───────┘
       │
       ├──────────► MySQL (Port 3306)
       │
       └──────────► FAISS (本地文件)
```
