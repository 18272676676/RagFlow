"""启动 RagFlow 服务器"""
import sys
import uvicorn
from pathlib import Path

# 添加项目根目录到路径
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

if __name__ == "__main__":
    print("=" * 60)
    print("启动 RagFlow 服务器")
    print("=" * 60)
    print("服务地址: http://localhost:8000")
    print("API 文档: http://localhost:8000/docs")
    print("上传页面: http://localhost:8000/static/upload.html")
    print("=" * 60)

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
