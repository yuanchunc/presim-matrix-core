"""
基础智能体模块

提供 Agent 抽象基类及默认实现 (消费者、决策者等)，
遵循 perceive -> think -> act 的认知循环。
"""

from presim_core.agents.base_agent import BaseAgent
from presim_core.agents.default_agents import ConsumerAgent, DecisionAgent

__all__ = [
    "BaseAgent",
    "ConsumerAgent",
    "DecisionAgent",
]
