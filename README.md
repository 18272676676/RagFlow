# RAG 知识库系统

基于 FastAPI 的单体 AI 知识库应用，使用 RAG（Retrieval-Augmented Generation）技术实现智能问答。

## 项目结构

```
RagFlow/
├── api/                    # API 层
│   ├── routes/            # 路由
│   │   ├── document.py    # 文档管理 API
│   │   └── qa.py          # 问答 API
│   └── __init__.py
├── config/                # 配置
│   ├── __init__.py
│   └── settings.py        # 配置管理
├── infrastructure/          # 基础设施层
│   ├── __init__.py
│   ├── database.py        # 数据库连接
│   └── logger.py          # 日志模块
├── models/                # 数据模型
│   ├── __init__.py
│   ├── db_models.py       # ORM 模型
│   ├── document.py        # 文档领域模型
│   └── qa.py              # 问答领域模型
├── services/              # 业务服务层
│   ├── __init__.py
│   ├── chunker.py         # 文档分块
│   ├── document_parser.py # 文档解析
│   ├── embedding.py       # Embedding 服务
│   ├── knowledge_builder.py # 知识构建
│   ├── llm.py            # LLM 调用
│   ├── prompt_builder.py  # Prompt 构建
│   ├── qa_service.py     # 问答服务
│   ├── retriever.py      # 检索模块
│   └── vector_store.py   # 向量库
├── static/               # 静态文件
│   ├── upload.html       # 上传页面
│   └── ask.html          # 问答页面
├── data/                 # 数据目录
│   ├── uploads/          # 上传文件
│   └── vector_store/     # 向量索引
├── logs/                 # 日志目录
├── main.py              # 主应用
├── init_db.py           # 数据库初始化
├── start_server.py      # 服务启动脚本
├── Dockerfile           # Docker 镜像
├── docker-compose.yml   # Docker Compose
├── requirements.txt     # Python 依赖
├── .env.example         # 环境变量示例
└── README.md           # 项目文档
```

## 技术栈

- **后端框架**: FastAPI
- **数据库**: MySQL 8.0
- **向量库**: FAISS
- **LLM**: DeepSeek API
- **Embedding**: sentence-transformers (text2vec-base-chinese)
- **部署**: Docker + Docker Compose

## 快速开始

### 1. 环境准备

确保已安装：
- Python 3.10+
- MySQL 8.0
- Docker（可选）

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件，配置以下参数：

```env
# 数据库配置
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=rag_knowledge_base

# DeepSeek API 配置
DEEPSEEK_API_BASE=https://api.deepseek.com/v1
DEEPSEEK_API_KEY=your_api_key
DEEPSEEK_MODEL=deepseek-chat

# 向量库配置
VECTOR_DB_TYPE=faiss
FAISS_INDEX_PATH=./data/vector_store/faiss_index
EMBEDDING_MODEL=shibing624/text2vec-base-chinese

# 其他配置...
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 初始化数据库

```bash
python init_db.py
```

> 这会自动创建所有数据表并初始化 admin 用户（用户名: `admin`，密码: `admin123`）

### 5. 启动服务

```bash
python start_server.py
```

或使用 uvicorn：

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 6. 访问应用

- 主页: http://localhost:8000
- 上传页面: http://localhost:8000/static/upload.html
- 问答页面: http://localhost:8000/static/ask.html
- API 文档: http://localhost:8000/docs

## Docker 部署

### 使用 Docker Compose

```bash
# 构建并启动
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

### 使用 Docker

```bash
# 构建镜像
docker build -t rag-knowledge-base .

# 运行容器
docker run -d \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  --env-file .env \
  rag-knowledge-base
```

## API 接口

### 文档管理

#### 上传文档
```http
POST /api/documents/upload
Content-Type: multipart/form-data

参数:
- file: 文件对象
```

#### 查询文档列表
```http
GET /api/documents?status=completed&skip=0&limit=10
```

#### 查询单个文档
```http
GET /api/documents/{document_id}
```

#### 删除文档
```http
DELETE /api/documents/{document_id}
```

#### 查询文档切片
```http
GET /api/documents/{document_id}/chunks
```

### 问答

#### 提问
```http
POST /api/qa/ask
Content-Type: application/json

{
  "question": "你的问题",
  "top_k": 5
}
```

#### 健康检查
```http
GET /api/qa/health
```

## 数据流

### 知识构建流程

```
用户上传文档
    ↓
保存文件到磁盘
    ↓
创建数据库记录（状态：pending）
    ↓
异步触发知识构建
    ↓
解析文档内容
    ↓
分块处理（Chunking）
    ↓
计算 Embedding
    ↓
存储到向量库
    ↓
更新数据库状态（completed/failed）
```

### 问答流程

```
用户提问
    ↓
对问题进行 Embedding
    ↓
向量相似度检索（Top-K）
    ↓
检索相关文档切片
    ↓
构建 Prompt（包含上下文）
    ↓
调用 LLM 生成答案
    ↓
返回答案 + 来源信息
```

## 模块说明

### 配置模块（config）
- **settings.py**: 集中管理所有配置项，通过环境变量管理

### 核心模块（core）
- **database.py**: 数据库连接和会话管理
- **logger.py**: 日志系统，支持 request_id 追踪

### 数据模型（models）
- **db_models.py**: 数据库 ORM 模型
- **document.py**: 文档领域模型
- **qa.py**: 问答领域模型

### 业务服务（services）
- **document_parser.py**: 文档解析（TXT/MD/PDF/DOCX）
- **chunker.py**: 文档分块（可配置大小和重叠）
- **embedding.py**: Embedding 服务（抽象接口）
- **vector_store.py**: 向量库（FAISS 实现，支持扩展）
- **knowledge_builder.py**: 知识构建流程编排
- **retriever.py**: 向量检索模块
- **prompt_builder.py**: Prompt 构建（System/Context/User 分离）
- **llm.py**: LLM 调用（DeepSeek 抽象层）
- **qa_service.py**: 问答服务编排

### API 层（api）
- **document.py**: 文档管理 HTTP 接口
- **qa.py**: 问答 HTTP 接口

## 特性

- 清晰的分层架构
- 模块边界明确，低耦合
- 支持多种文档格式
- 可配置的分块策略
- 向量相似度检索
- 完整的问答流程
- 日志追踪（request_id）
- Docker 部署支持
- 友好的 Web 界面

## 注意事项

1. 首次启动会下载 Embedding 模型，需要等待一段时间
2. DeepSeek API 需要有效的 API Key
3. 文档处理是异步的，上传后请等待状态变为 completed
4. FAISS 索引文件存储在 `data/vector_store` 目录

## 故障排除

### 数据库连接失败
- 检查 MySQL 服务是否启动
- 验证数据库配置是否正确
- 确认数据库用户权限

### Embedding 模型加载失败
- 检查网络连接
- 确认有足够的磁盘空间
- 可以尝试手动下载模型

### LLM 调用失败
- 验证 API Key 是否正确
- 检查网络连接
- 查看 API 配额

## 扩展建议

- 支持 Rerank
- 添加文档版本管理
- 支持批量上传
- 添加知识图谱
- 支持多种向量库（Milvus/Chroma）
