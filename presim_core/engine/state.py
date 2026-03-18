"""
全局状态定义 - State / Context

定义仿真运行过程中的共享状态结构，
供 LangGraph 各节点读写，实现状态流转。
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SimulationState(BaseModel):
    """
    仿真全局状态

    贯穿整个仿真流程的共享上下文，包含:
    - 配置参数
    - 时序数据
    - 智能体输出
    - 中间结果
    """

    # 仿真配置 (来自 config.yaml 等)
    config: Dict[str, Any] = Field(default_factory=dict, description="仿真初始参数配置")

    # 当前仿真步数
    step: int = Field(default=0, description="当前执行的仿真步数")

    # 时序结果 (每步的输出，用于绘图)
    timeline: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="按时间步记录的仿真结果序列",
    )

    # 智能体输出缓存
    agent_outputs: Dict[str, Any] = Field(
        default_factory=dict,
        description="各智能体节点的输出结果",
    )

    # 上下文/记忆引用 (可选，供闭源模块扩展)
    context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="扩展上下文，预留给闭源模块",
    )

    # 错误与中断标记
    error: Optional[str] = Field(default=None, description="运行过程中的错误信息")
    stopped: bool = Field(default=False, description="是否已主动停止仿真")

    # 历史事件与结构化结果（StateResolve 节点更新）
    history_events: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="历史事件序列，用于因果链路分析",
    )
    simulation_results: Dict[str, Any] = Field(
        default_factory=dict,
        description="结构化的仿真结果指标",
    )

    class Config:
        """Pydantic 配置"""
        arbitrary_types_allowed = True
        extra = "allow"  # 允许闭源模块扩展字段
