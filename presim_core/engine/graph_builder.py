"""
仿真调度引擎 - LangGraph 多轮时序仿真

基于 LangGraph 实现状态流转，集成生命周期钩子与扩展注册表，
实现开源内核与闭源模块的解耦扩展。
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Iterator, List, Optional, TypedDict

from presim_core.engine.state import SimulationState
from presim_core.engine.hooks import (
    EngineHooks,
    apply_hook_result_to_state,
)
from presim_core.registry import get_registry

logger = logging.getLogger(__name__)

# LangGraph 状态 schema（TypedDict 便于部分更新）
class GraphState(TypedDict, total=False):
    """LangGraph 图状态，与 SimulationState 字段对应"""

    config: Dict[str, Any]
    step: int
    timeline: List[Dict[str, Any]]
    agent_outputs: Dict[str, Any]
    context: Optional[Dict[str, Any]]
    error: Optional[str]
    stopped: bool
    history_events: List[Dict[str, Any]]
    simulation_results: Dict[str, Any]


def _state_to_dict(state: SimulationState) -> GraphState:
    """SimulationState -> GraphState dict"""
    return GraphState(
        config=state.config,
        step=state.step,
        timeline=state.timeline,
        agent_outputs=state.agent_outputs,
        context=state.context,
        error=state.error,
        stopped=state.stopped,
        history_events=state.history_events,
        simulation_results=state.simulation_results,
    )


def _dict_to_state(d: Dict[str, Any]) -> SimulationState:
    """GraphState dict -> SimulationState"""
    return SimulationState(
        config=d.get("config", {}),
        step=d.get("step", 0),
        timeline=d.get("timeline", []),
        agent_outputs=d.get("agent_outputs", {}),
        context=d.get("context"),
        error=d.get("error"),
        stopped=d.get("stopped", False),
        history_events=d.get("history_events", []),
        simulation_results=d.get("simulation_results", {}),
    )


def _merge_updates(base: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    """合并状态更新，支持嵌套 dict 的浅合并"""
    result = dict(base)
    for k, v in updates.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = {**result[k], **v}
        else:
            result[k] = v
    return result


# =============================================================================
# 核心节点实现
# =============================================================================


class _NodeContext:
    """节点执行上下文，持有 registry、hooks 等"""

    def __init__(
        self,
        registry: Any,
        hooks: EngineHooks,
        agent_types: List[str],
        max_steps: int,
        parallel_agents: bool = False,
    ) -> None:
        self.registry = registry
        self.hooks = hooks
        self.agent_types = agent_types
        self.max_steps = max_steps
        self.parallel_agents = parallel_agents
        self._paused = False
        self._stop_requested = False

    def request_pause(self) -> None:
        self._paused = True

    def request_stop(self) -> None:
        self._stop_requested = True

    @property
    def paused(self) -> bool:
        return self._paused

    @property
    def stop_requested(self) -> bool:
        return self._stop_requested


def _environment_update_node(state: GraphState, ctx: _NodeContext) -> GraphState:
    """
    节点1：EnvironmentUpdate - 环境更新

    基于上一轮结果、事件、外部注入更新全局环境。
    支持通过注册表 get_env_updater 扩展。
    """
    sim_state = _dict_to_state(state)
    hook_result = ctx.hooks.before_step_start(sim_state, state.get("step", 0))
    if hook_result.state_updates:
        state = _merge_updates(state, hook_result.state_updates)

    updater = ctx.registry.get_env_updater()
    if updater and hasattr(updater, "update"):
        try:
            updates = updater.update(sim_state)
            if updates:
                state = _merge_updates(state, updates)
        except Exception as e:
            logger.warning("环境更新器执行失败: %s", e)

    # 默认：简单传递，无额外环境变化
    return state


def _agent_interaction_node(state: GraphState, ctx: _NodeContext) -> GraphState:
    """
    节点2：AgentInteraction - 智能体交互

    遍历智能体，执行 perceive->think->act，收集行动结果。
    每个智能体前后执行 before_agent_act、after_agent_act 钩子。
    """
    sim_state = _dict_to_state(state)
    step = state.get("step", 0)
    agent_outputs = dict(state.get("agent_outputs", {}))

    for agent_type in ctx.agent_types:
        try:
            agent = ctx.registry.create_agent(agent_type)
            agent_name = getattr(agent, "name", agent_type)

            # before_agent_act
            hr_before = ctx.hooks.before_agent_act(sim_state, step, agent_name)
            if hr_before.state_updates:
                sim_state = apply_hook_result_to_state(sim_state, hr_before)
                state = _merge_updates(state, hr_before.state_updates or {})

            # perceive -> think -> act
            action_result = agent.run(sim_state)

            # after_agent_act
            hr_after = ctx.hooks.after_agent_act(sim_state, step, agent_name, action_result)
            if hr_after.state_updates:
                state = _merge_updates(state, hr_after.state_updates or {})

            # 合并 agent 输出
            if isinstance(action_result, dict) and "agent_outputs" in action_result:
                agent_outputs.update(action_result["agent_outputs"])
            else:
                agent_outputs[agent_name] = action_result

        except Exception as e:
            logger.exception("智能体 %s 执行失败: %s", agent_type, e)
            agent_outputs[agent_type] = {"error": str(e)}

    return _merge_updates(state, {"agent_outputs": agent_outputs})


def _state_resolve_node(state: GraphState, ctx: _NodeContext) -> GraphState:
    """
    节点3：StateResolve - 状态汇总与解析

    汇总智能体输出，转化为结构化状态，更新 timeline、history_events、simulation_results。
    """
    sim_state = _dict_to_state(state)
    parser = ctx.registry.get_parser()

    timeline = list(state.get("timeline", []))
    history_events = list(state.get("history_events", []))
    simulation_results = dict(state.get("simulation_results", {}))

    step = state.get("step", 0)
    agent_outputs = state.get("agent_outputs", {})

    # 提取结构化结果
    step_record: Dict[str, Any] = {"step": step, "agent_outputs": agent_outputs}
    timeline.append(step_record)
    history_events.append({"step": step, "type": "step_complete", "data": step_record})

    # 使用解析器提取指标
    if hasattr(parser, "parse_timeline"):
        parsed = parser.parse_timeline(sim_state)
        if parsed:
            simulation_results["timeline"] = parsed
    simulation_results["steps_completed"] = step + 1

    next_step = step + 1
    updates: Dict[str, Any] = {
        "step": next_step,
        "timeline": timeline,
        "history_events": history_events,
        "simulation_results": simulation_results,
    }

    # 执行 after_step_end 钩子
    sim_state_updated = _dict_to_state(_merge_updates(state, updates))
    hr = ctx.hooks.after_step_end(sim_state_updated, step)
    if hr.state_updates:
        updates = _merge_updates(updates, hr.state_updates)

    return _merge_updates(state, updates)


def _should_continue(state: GraphState, ctx: _NodeContext) -> str:
    """
    终止条件判断

    返回 "continue" 继续下一轮，"end" 结束仿真。
    step 在 state_resolve 中已更新为 next_step，故 step >= max_steps 时终止。
    """
    if ctx.stop_requested or state.get("stopped"):
        return "end"
    if state.get("error"):
        return "end"
    step = state.get("step", 0)
    if step >= ctx.max_steps:
        return "end"
    return "continue"


# =============================================================================
# SimulationEngine
# =============================================================================


class SimulationEngine:
    """
    仿真引擎 - 封装 LangGraph 构建、编译、运行全流程

    对外提供 run、arun、stream 等极简接口，屏蔽内部实现。
    支持暂停、终止、断点续跑。
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        agent_types: Optional[List[str]] = None,
        initial_state: Optional[SimulationState] = None,
        max_steps: int = 12,
        parallel_agents: bool = False,
    ) -> None:
        """
        初始化仿真引擎

        Args:
            config: 仿真配置，将写入 state.config
            agent_types: 智能体类型列表，如 ["consumer", "decision"]
            initial_state: 初始状态，None 时从 config 构建
            max_steps: 最大仿真轮次
            parallel_agents: 是否并行执行智能体（当前实现为串行）
        """
        self._config = config or {}
        self._agent_types = agent_types or ["consumer", "decision"]
        self._max_steps = max_steps
        self._parallel_agents = parallel_agents

        self._registry = get_registry()
        self._hooks = EngineHooks()

        self._ctx = _NodeContext(
            registry=self._registry,
            hooks=self._hooks,
            agent_types=self._agent_types,
            max_steps=max_steps,
            parallel_agents=parallel_agents,
        )

        if initial_state is not None:
            self._initial_state = initial_state
        else:
            self._initial_state = SimulationState(
                config=self._config,
                step=0,
            )

        self._graph = None
        self._built = False

    def build_graph(self) -> "SimulationEngine":
        """
        构建 LangGraph 状态图

        添加 4 个核心节点及边，编译成可执行图。
        若 LangGraph 未安装，则使用纯 Python 循环 fallback。
        """
        def env_node(s: GraphState) -> GraphState:
            return _environment_update_node(s, self._ctx)

        def agent_node(s: GraphState) -> GraphState:
            return _agent_interaction_node(s, self._ctx)

        def resolve_node(s: GraphState) -> GraphState:
            return _state_resolve_node(s, self._ctx)

        def route_after_resolve(s: GraphState) -> str:
            return _should_continue(s, self._ctx)

        try:
            from langgraph.graph import StateGraph, START, END

            builder = StateGraph(GraphState)
            builder.add_node("environment_update", env_node)
            builder.add_node("agent_interaction", agent_node)
            builder.add_node("state_resolve", resolve_node)
            builder.add_edge(START, "environment_update")
            builder.add_edge("environment_update", "agent_interaction")
            builder.add_edge("agent_interaction", "state_resolve")
            builder.add_conditional_edges(
                "state_resolve",
                route_after_resolve,
                {"continue": "environment_update", "end": END},
            )
            self._graph = builder.compile()
            logger.info("仿真图构建完成 (LangGraph)")
        except ImportError:
            self._graph = None
            logger.info("LangGraph 未安装，使用纯 Python 循环实现")

        self._built = True
        return self

    def _ensure_built(self) -> None:
        if not self._built or self._graph is None:
            self.build_graph()

    def _prepare_initial_state(self) -> Dict[str, Any]:
        """准备初始状态，执行 before_simulation_start 钩子"""
        state = self._initial_state
        hr = self._hooks.before_simulation_start(state)
        if hr.state_updates:
            state = apply_hook_result_to_state(state, hr)
        if hr.stop:
            state = state.model_copy(update={"stopped": True})
        return _state_to_dict(state)

    def _run_loop_manual(self, initial: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
        """
        无 LangGraph 时的纯 Python 循环实现（fallback）

        用于 LangGraph 未安装或需简化部署时。
        """
        state = dict(initial)
        step = 0

        while step < self._max_steps and not self._ctx.stop_requested and not state.get("stopped"):
            state["step"] = step

            # EnvironmentUpdate
            state = _merge_updates(state, _environment_update_node(state, self._ctx))

            # AgentInteraction
            state = _merge_updates(state, _agent_interaction_node(state, self._ctx))

            # StateResolve
            state = _merge_updates(state, _state_resolve_node(state, self._ctx))

            yield state
            step += 1

            if _should_continue(state, self._ctx) == "end":
                break

        # before_simulation_end
        sim_state = _dict_to_state(state)
        hr = self._hooks.before_simulation_end(sim_state)
        if hr.state_updates:
            state = _merge_updates(state, hr.state_updates or {})
        yield state

    def run(
        self,
        *,
        resume_from: Optional[SimulationState] = None,
    ) -> tuple[SimulationState, Dict[str, Any]]:
        """
        同步运行完整仿真

        Args:
            resume_from: 断点续跑时的已有状态

        Returns:
            (最终仿真状态, 结构化结果)
        """
        if resume_from is not None:
            self._initial_state = resume_from

        initial = self._prepare_initial_state()
        if initial.get("stopped"):
            return _dict_to_state(initial), initial.get("simulation_results", {})

        try:
            self._ensure_built()
            if self._graph is not None:
                final = self._graph.invoke(initial)
            else:
                final = {}
                for s in self._run_loop_manual(initial):
                    final = s
        except Exception as e:
            logger.exception("仿真执行异常: %s", e)
            sim_state = _dict_to_state(initial)
            self._hooks.on_simulation_error(sim_state, e)
            return sim_state.model_copy(update={"error": str(e)}), {}

        sim_state = _dict_to_state(final)
        hr = self._hooks.before_simulation_end(sim_state)
        if hr.state_updates:
            sim_state = apply_hook_result_to_state(sim_state, hr)

        return sim_state, sim_state.simulation_results

    async def arun(
        self,
        *,
        resume_from: Optional[SimulationState] = None,
    ) -> tuple[SimulationState, Dict[str, Any]]:
        """异步运行仿真"""
        return await asyncio.to_thread(self.run, resume_from=resume_from)

    def stream(
        self,
        *,
        resume_from: Optional[SimulationState] = None,
    ) -> Iterator[tuple[int, SimulationState]]:
        """
        流式返回每步进度

        适配 Streamlit 等实时展示。每 yield 一次为一步完成。
        """
        if resume_from is not None:
            self._initial_state = resume_from

        initial = self._prepare_initial_state()
        if initial.get("stopped"):
            yield 0, _dict_to_state(initial)
            return

        try:
            self._ensure_built()
            if self._graph is not None and hasattr(self._graph, "stream"):
                for event in self._graph.stream(initial):
                    for node_name, node_state in event.items():
                        # 仅在 state_resolve 后 yield（每步完成）
                        if node_name == "state_resolve":
                            step = node_state.get("step", 0)
                            yield step, _dict_to_state(node_state)
            else:
                for s in self._run_loop_manual(initial):
                    yield s.get("step", 0), _dict_to_state(s)
        except Exception as e:
            logger.exception("仿真流式执行异常: %s", e)
            self._hooks.on_simulation_error(_dict_to_state(initial), e)
            raise

    def pause(self) -> None:
        """请求暂停（下一轮开始前生效）"""
        self._ctx.request_pause()

    def stop(self) -> None:
        """请求终止仿真"""
        self._ctx.request_stop()


# =============================================================================
# 兼容层：GraphBuilder
# =============================================================================


class GraphBuilder:
    """
    图构建器（兼容层）

    保留原有接口，内部委托给 SimulationEngine。
    """

    def __init__(self) -> None:
        self._engine: Optional[SimulationEngine] = None

    def build(self) -> SimulationEngine:
        """构建并返回可运行的仿真引擎"""
        self._engine = SimulationEngine()
        return self._engine.build_graph()


# =============================================================================
# 测试用例
# =============================================================================

if __name__ == "__main__":
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    logging.basicConfig(level=logging.INFO)

    config = {
        "simulation": {"steps": 3, "seed": 42},
        "pricing": {"base_price": 12},
    }
    engine = SimulationEngine(
        config=config,
        agent_types=["consumer", "decision"],
        max_steps=3,
    )
    engine.build_graph()
    final_state, results = engine.run()
    print("step:", final_state.step)
    print("timeline steps:", len(final_state.timeline))
    print("simulation_results:", results)
    print("OK")
