"""
仿真引擎内核 - LangGraph 调度

负责构建和管理仿真状态图，定义节点流转逻辑，
协调智能体执行与生命周期钩子调用。
"""

from presim_core.engine.graph_builder import GraphBuilder, SimulationEngine
from presim_core.engine.state import SimulationState
from presim_core.engine.hooks import (
    EngineHooks,
    HookContext,
    HookManager,
    HookResult,
    get_hook_manager,
    apply_hook_result_to_state,
    HOOK_BEFORE_SIMULATION_START,
    HOOK_BEFORE_STEP_START,
    HOOK_BEFORE_AGENT_ACT,
    HOOK_AFTER_AGENT_ACT,
    HOOK_AFTER_STEP_END,
    HOOK_BEFORE_SIMULATION_END,
    HOOK_ON_SIMULATION_ERROR,
)

__all__ = [
    "GraphBuilder",
    "SimulationEngine",
    "SimulationState",
    "EngineHooks",
    "HookContext",
    "HookManager",
    "HookResult",
    "get_hook_manager",
    "apply_hook_result_to_state",
    "HOOK_BEFORE_SIMULATION_START",
    "HOOK_BEFORE_STEP_START",
    "HOOK_BEFORE_AGENT_ACT",
    "HOOK_AFTER_AGENT_ACT",
    "HOOK_AFTER_STEP_END",
    "HOOK_BEFORE_SIMULATION_END",
    "HOOK_ON_SIMULATION_ERROR",
]
