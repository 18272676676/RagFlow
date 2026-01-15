"""
文档分块模块

解决什么问题:
1. 将长文档切分成适合 Embedding 的文本块
2. 保持上下文连贯性，避免语义断裂
3. 可配置的块大小和重叠度，适应不同场景

为什么现在需要:
- LLM 有上下文长度限制，长文档必须分块
- Embedding 模型对长度敏感，过长的块效果差
- 适当的重叠可以保留上下文信息
"""

from typing import List
from dataclasses import dataclass
import re
from RagFlow.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Chunk:
    """文本块"""
    index: int  # 块序号
    text: str  # 块文本内容
    start_pos: int  # 原文中起始位置
    end_pos: int  # 原文中结束位置


class Chunker:
    """文档分块器"""

    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        separator: str = "\n\n"
    ):
        """
        初始化分块器

        Args:
            chunk_size: 块大小（字符数）
            chunk_overlap: 块重叠大小（字符数）
            separator: 分隔符，优先按分隔符切分
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separator = separator

    def chunk(self, text: str) -> List[Chunk]:
        """
        将文本切分成块

        Args:
            text: 待分块的文本

        Returns:
            文本块列表
        """
        if not text or not text.strip():
            return []

        # 清理文本
        text = self._clean_text(text)

        # 如果文本长度小于 chunk_size，直接返回一个块
        if len(text) <= self.chunk_size:
            return [Chunk(index=0, text=text, start_pos=0, end_pos=len(text))]

        # 按分隔符分割
        chunks = self._chunk_by_separator(text)

        # 如果没有分隔符或分割效果不好，按字符分割
        if not chunks or len(chunks) == 1:
            chunks = self._chunk_by_characters(text)

        return chunks

    def _clean_text(self, text: str) -> str:
        """
        清理文本

        Args:
            text: 原始文本

        Returns:
            清理后的文本
        """
        # 去除多余空行
        text = re.sub(r"\n{3,}", "\n\n", text)
        # 去除行首行尾空格
        text = "\n".join(line.strip() for line in text.split("\n"))
        return text.strip()

    def _chunk_by_separator(self, text: str) -> List[Chunk]:
        """
        按分隔符切分

        Args:
            text: 文本内容

        Returns:
            文本块列表
        """
        chunks = []
        separator_parts = text.split(self.separator)

        current_chunk = ""
        current_start = 0
        chunk_index = 0

        for part in separator_parts:
            part = part.strip()
            if not part:
                continue

            # 如果当前块加入这部分后超过 chunk_size，保存当前块
            if len(current_chunk) + len(part) > self.chunk_size and current_chunk:
                chunks.append(Chunk(
                    index=chunk_index,
                    text=current_chunk.strip(),
                    start_pos=current_start,
                    end_pos=current_start + len(current_chunk)
                ))
                chunk_index += 1

                # 计算下一块的起始位置（考虑重叠）
                overlap_start = max(0, len(current_chunk) - self.chunk_overlap)
                current_start += overlap_start
                current_chunk = current_chunk[overlap_start:]

            current_chunk += part + self.separator

        # 添加最后一个块
        if current_chunk.strip():
            chunks.append(Chunk(
                index=chunk_index,
                text=current_chunk.strip(),
                start_pos=current_start,
                end_pos=current_start + len(current_chunk)
            ))

        return chunks

    def _chunk_by_characters(self, text: str) -> List[Chunk]:
        """
        按字符切分（当没有分隔符时使用）

        Args:
            text: 文本内容

        Returns:
            文本块列表
        """
        chunks = []
        start = 0
        chunk_index = 0

        while start < len(text):
            end = start + self.chunk_size

            # 如果不是最后一块，尝试在句号、问号、感叹号处切分
            if end < len(text):
                # 在块结尾附近寻找标点符号
                for i in range(end, max(start + self.chunk_size // 2, end - 100), -1):
                    if text[i] in ["。", "！", "？", ".", "!", "?", "\n"]:
                        end = i + 1
                        break

            chunk = Chunk(
                index=chunk_index,
                text=text[start:end].strip(),
                start_pos=start,
                end_pos=end
            )
            chunks.append(chunk)

            start = end - self.chunk_overlap
            chunk_index += 1

        return chunks
