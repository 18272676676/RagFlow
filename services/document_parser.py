"""
文档解析模块

解决什么问题:
1. 解析不同格式的文档，提取纯文本内容
2. 统一解析接口，便于扩展新格式
3. 处理解析过程中的异常和错误

为什么现在需要:
- 用户上传的文档格式多样，需要统一解析
- 解析是知识构建的第一步，必须在 Embedding 之前
- 扩展新格式时不需要修改业务逻辑
"""

from typing import Optional
from abc import ABC, abstractmethod
import io
from RagFlow.core.logger import get_logger

logger = get_logger(__name__)


class DocumentParser(ABC):
    """文档解析器抽象基类"""

    @abstractmethod
    def parse(self, file_content: bytes) -> str:
        """
        解析文档内容

        Args:
            file_content: 文档字节数据

        Returns:
            解析后的文本内容
        """
        pass


class TxtParser(DocumentParser):
    """TXT 文本解析器"""

    def parse(self, file_content: bytes) -> str:
        """解析 TXT 文件"""
        try:
            return file_content.decode("utf-8")
        except UnicodeDecodeError:
            # 尝试其他编码
            try:
                return file_content.decode("gbk")
            except UnicodeDecodeError:
                return file_content.decode("latin-1")


class MarkdownParser(DocumentParser):
    """Markdown 文本解析器"""

    def parse(self, file_content: bytes) -> str:
        """解析 Markdown 文件"""
        try:
            return file_content.decode("utf-8")
        except UnicodeDecodeError:
            try:
                return file_content.decode("gbk")
            except UnicodeDecodeError:
                return file_content.decode("latin-1")


class PDFParser(DocumentParser):
    """PDF 文本解析器"""

    def parse(self, file_content: bytes) -> str:
        """解析 PDF 文件"""
        try:
            import PyPDF2

            pdf_file = io.BytesIO(file_content)
            pdf_reader = PyPDF2.PdfReader(pdf_file)

            text_parts = []
            for page in pdf_reader.pages:
                text_parts.append(page.extract_text())

            return "\n".join(text_parts)
        except Exception as e:
            logger.error(f"PDF 解析失败: {e}")
            raise ValueError(f"PDF 解析失败: {e}")


class DocxParser(DocumentParser):
    """Word 文本解析器"""

    def parse(self, file_content: bytes) -> str:
        """解析 Word 文件"""
        try:
            import docx

            doc_file = io.BytesIO(file_content)
            doc = docx.Document(doc_file)

            text_parts = []
            for paragraph in doc.paragraphs:
                text_parts.append(paragraph.text)

            return "\n".join(text_parts)
        except Exception as e:
            logger.error(f"Word 解析失败: {e}")
            raise ValueError(f"Word 解析失败: {e}")


class DocumentParserFactory:
    """文档解析器工厂"""

    # 支持的文件类型与解析器映射（使用不带点的扩展名）
    _parsers = {
        "txt": TxtParser(),
        "md": MarkdownParser(),
        "pdf": PDFParser(),
        "docx": DocxParser(),
    }

    @classmethod
    def get_parser(cls, file_name: str) -> Optional[DocumentParser]:
        """
        根据文件名获取对应的解析器

        Args:
            file_name: 文件名

        Returns:
            对应的解析器实例，如果不支持则返回 None
        """
        file_ext = cls._get_file_extension(file_name)
        return cls._parsers.get(file_ext)

    @classmethod
    def is_supported(cls, file_name: str) -> bool:
        """
        判断文件类型是否支持

        Args:
            file_name: 文件名

        Returns:
            是否支持该文件类型
        """
        file_ext = cls._get_file_extension(file_name)
        return file_ext in cls._parsers

    @classmethod
    def _get_file_extension(cls, file_name: str) -> str:
        """获取文件扩展名（小写）"""
        return file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""

    @classmethod
    def get_supported_extensions(cls) -> list:
        """获取所有支持的文件扩展名（带点）"""
        return ["." + ext for ext in cls._parsers.keys()]
