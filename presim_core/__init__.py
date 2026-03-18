"""
预演沙盘 PreSim Matrix - 核心代码库

100% 开源内核，采用微内核 + 插件注册表架构，
严格实现开源内核与闭源商业模块的解耦。

主要子模块:
- engine: 仿真引擎内核 (LangGraph 调度)
- agents: 基础智能体模块
- llm: 大模型统一适配层
- memory: 记忆与存储层 (Chroma)
- parser: 结果解析与评估
- registry: 扩展注册表（闭源模块唯一入口）
"""

__version__ = "0.1.0"

from presim_core.registry import (
    ExtensionRegistry,
    ExtensionModule,
    get_registry,
    Registry,
)

# 全局注册表单例，方便扩展模块直接使用
registry = get_registry()

__all__ = [
    "__version__",
    "ExtensionRegistry",
    "ExtensionModule",
    "get_registry",
    "registry",
    "Registry",
]
