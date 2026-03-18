"""
基础消费者、决策者 Agent 实现

提供开源内核的默认智能体，用于 Demo 和基础仿真场景。
商业模块可注册更复杂的 Agent 实现。
"""

from typing import Any, Dict

from presim_core.agents.base_agent import BaseAgent
from presim_core.engine.state import SimulationState


class ConsumerAgent(BaseAgent):
    """
    基础消费者 Agent

    模拟消费者在仿真中的决策行为 (如购买意愿、选择偏好)。
    """

    @property
    def name(self) -> str:
        return "consumer"

    def perceive(self, state: SimulationState) -> Dict[str, Any]:
        """感知: 获取当前定价、环境等信息"""
        return {
            "config": state.config,
            "step": state.step,
            "timeline": state.timeline,
        }

    def think(self, perception: Dict[str, Any], state: SimulationState) -> Dict[str, Any]:
        """思考: 基于感知进行简单推理 (可接入 LLM)"""
        return {"perception": perception}

    def act(self, thought: Dict[str, Any], state: SimulationState) -> Dict[str, Any]:
        """行动: 输出消费者决策结果"""
        return {
            "agent_outputs": {
                **state.agent_outputs,
                self.name: {"thought": thought},
            }
        }


class DecisionAgent(BaseAgent):
    """
    基础决策者 Agent

    模拟经营者/决策者在仿真中的决策行为 (如定价、选址)。
    """

    @property
    def name(self) -> str:
        return "decision"

    def perceive(self, state: SimulationState) -> Dict[str, Any]:
        """感知: 获取市场反馈、历史数据等"""
        return {
            "config": state.config,
            "step": state.step,
            "timeline": state.timeline,
            "agent_outputs": state.agent_outputs,
        }

    def think(self, perception: Dict[str, Any], state: SimulationState) -> Dict[str, Any]:
        """思考: 基于市场反馈进行决策推理"""
        return {"perception": perception}

    def act(self, thought: Dict[str, Any], state: SimulationState) -> Dict[str, Any]:
        """行动: 输出决策结果 (如新定价、策略调整)"""
        return {
            "agent_outputs": {
                **state.agent_outputs,
                self.name: {"thought": thought},
            }
        }
