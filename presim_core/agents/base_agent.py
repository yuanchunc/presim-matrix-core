"""
Agent 抽象基类

定义 perceive -> think -> act 的认知循环接口，
所有智能体实现必须继承此类并实现抽象方法。
"""

from abc import ABC, abstractmethod
from typing import Any, Dict

from presim_core.engine.state import SimulationState


class BaseAgent(ABC):
    """
    智能体抽象基类

    遵循认知循环: perceive(感知) -> think(思考) -> act(行动)
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """智能体唯一标识"""
        pass

    @abstractmethod
    def perceive(self, state: SimulationState) -> Dict[str, Any]:
        """
        感知阶段 - 从环境中获取信息

        Args:
            state: 当前仿真状态

        Returns:
            感知到的信息字典
        """
        pass

    @abstractmethod
    def think(self, perception: Dict[str, Any], state: SimulationState) -> Dict[str, Any]:
        """
        思考阶段 - 基于感知进行推理

        Args:
            perception: 感知结果
            state: 当前仿真状态

        Returns:
            思考/推理结果
        """
        pass

    @abstractmethod
    def act(self, thought: Dict[str, Any], state: SimulationState) -> Dict[str, Any]:
        """
        行动阶段 - 输出决策或行为

        Args:
            thought: 思考结果
            state: 当前仿真状态

        Returns:
            状态更新字典，将合并到 SimulationState
        """
        pass

    def run(self, state: SimulationState) -> Dict[str, Any]:
        """
        执行完整认知循环: perceive -> think -> act

        Args:
            state: 当前仿真状态

        Returns:
            最终的状态更新
        """
        perception = self.perceive(state)
        thought = self.think(perception, state)
        return self.act(thought, state)
