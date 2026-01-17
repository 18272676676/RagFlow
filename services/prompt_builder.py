"""
Prompt 构建模块

解决什么问题:
1. 构建 RAG 对话的提示词模板
2. 分离 System、Context、User 三部分内容
3. 统一 Prompt 格式，便于维护和优化

为什么现在需要:
- Prompt 质量直接影响回答质量，需要独立管理
- 避免 Prompt 硬编码在业务代码中，难以维护
- 便于 A/B 测试和 Prompt 版本管理
"""

from typing import List, Dict
from RagFlow.core.logger import get_logger

logger = get_logger(__name__)


class PromptBuilder:
    """Prompt 构建器"""

    SYSTEM_PROMPT_TEMPLATE = """你是一个专业的知识库助手。请仔细阅读提供的上下文信息，基于这些信息回答用户的问题。

【回答要求】
1. 回答必须基于提供的上下文信息，不要编造内容
2. 如果上下文中没有相关信息，请明确说明"上下文中没有找到相关信息"
3. 回答要准确、清晰、有条理
4. 可以适当引用上下文中的关键信息
5. 保持专业和友好的语气"""

    CONTEXT_TEMPLATE = """【知识库上下文】
{context}"""

    USER_QUESTION_TEMPLATE = """【用户问题】
{question}

请基于上述上下文信息回答用户的问题："""

    def __init__(
        self,
        system_prompt: str = None,
        context_template: str = None,
        user_question_template: str = None
    ):
        """
        初始化 Prompt 构建器

        Args:
            system_prompt: System 提示词模板
            context_template: Context 提示词模板
            user_question_template: User 问题模板
        """
        self.system_prompt = system_prompt or self.SYSTEM_PROMPT_TEMPLATE
        self.context_template = context_template or self.CONTEXT_TEMPLATE
        self.user_question_template = user_question_template or self.USER_QUESTION_TEMPLATE

    def build(
        self,
        context_chunks: List[str],
        question: str,
        max_context_length: int = 8000
    ) -> List[Dict]:
        """
        构建对话消息列表（带知识库上下文）

        Args:
            context_chunks: 上下文切片列表
            question: 用户问题
            max_context_length: 最大上下文长度

        Returns:
            消息列表，包含 system、user 消息
        """
        # 构建 context 文本
        context_text = self._build_context(context_chunks, max_context_length)

        # 构建消息列表
        messages = [
            {
                "role": "system",
                "content": self.system_prompt
            },
            {
                "role": "user",
                "content": self._build_user_message(context_text, question)
            }
        ]

        logger.info(f"构建 Prompt 成功，上下文长度: {len(context_text)}")
        return messages

    def build_without_context(
        self,
        question: str
    ) -> List[Dict]:
        """
        构建对话消息列表（无知识库上下文，直接使用大模型回答）

        Args:
            question: 用户问题

        Returns:
            消息列表，包含 system、user 消息
        """
        # 无上下文时的 system prompt
        system_prompt = """你是一个智能助手，能够回答各种问题。

【回答要求】
1. 回答要准确、清晰、有条理
2. 保持专业和友好的语气
3. 可以根据你的知识库回答任何问题
4. 对于日期时间类问题，请给出准确的答案"""

        # 构建消息列表
        messages = [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": f"【用户问题】\n{question}\n\n请回答用户的问题："
            }
        ]

        logger.info(f"构建无上下文 Prompt 成功")
        return messages

    def _build_context(
        self,
        context_chunks: List[str],
        max_length: int
    ) -> str:
        """
        构建上下文文本

        Args:
            context_chunks: 上下文切片列表
            max_length: 最大长度

        Returns:
            上下文文本
        """
        if not context_chunks:
            return "（暂无上下文信息）"

        # 拼接所有上下文
        full_context = "\n\n---\n\n".join(context_chunks)

        # 截断超长上下文
        if len(full_context) > max_length:
            full_context = full_context[:max_length] + "..."

        return full_context

    def _build_user_message(self, context_text: str, question: str) -> str:
        """
        构建用户消息

        Args:
            context_text: 上下文文本
            question: 用户问题

        Returns:
            用户消息内容
        """
        context_part = self.context_template.format(context=context_text)
        question_part = self.user_question_template.format(question=question)

        return f"{context_part}\n\n{question_part}"

    def set_system_prompt(self, system_prompt: str):
        """设置 System 提示词"""
        self.system_prompt = system_prompt
        logger.info("更新 System 提示词")

    def set_context_template(self, context_template: str):
        """设置 Context 模板"""
        self.context_template = context_template
        logger.info("更新 Context 模板")

    def set_user_question_template(self, user_question_template: str):
        """设置 User 问题模板"""
        self.user_question_template = user_question_template
        logger.info("更新 User 问题模板")


class PromptBuilderFactory:
    """Prompt 构建器工厂"""

    @staticmethod
    def create_default() -> PromptBuilder:
        """创建默认 Prompt 构建器"""
        return PromptBuilder()

    @staticmethod
    def create_custom(
        system_prompt: str,
        context_template: str = None,
        user_question_template: str = None
    ) -> PromptBuilder:
        """创建自定义 Prompt 构建器"""
        return PromptBuilder(
            system_prompt=system_prompt,
            context_template=context_template,
            user_question_template=user_question_template
        )
