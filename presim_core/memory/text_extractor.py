"""
基础信息提取

从文本或结构化数据中提取关键信息，
用于记忆存储或 Agent 上下文增强。
"""

from typing import Any, Dict, List, Optional


class TextExtractor:
    """
    基础文本/信息提取器

    提供简单的规则或模板提取能力，
    复杂场景可由闭源模块扩展。
    """

    def extract_key_values(self, text: str, keys: List[str]) -> Dict[str, Any]:
        """
        从文本中提取指定键对应的值

        Args:
            text: 输入文本
            keys: 要提取的键名列表

        Returns:
            键值对字典，未找到的键值为 None
        """
        result: Dict[str, Any] = {k: None for k in keys}
        # 简单实现: 可按需扩展正则或 LLM 抽取
        for key in keys:
            if key in text:
                # 占位逻辑，实际可接入更复杂的解析
                result[key] = text
        return result

    def extract_from_dict(self, data: Dict[str, Any], path: str) -> Optional[Any]:
        """
        从嵌套字典中按路径提取值

        Args:
            data: 嵌套字典
            path: 点分路径，如 "config.pricing.base"

        Returns:
            提取的值，不存在则返回 None
        """
        parts = path.split(".")
        current: Any = data
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current
