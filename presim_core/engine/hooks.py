"""
仿真全流程生命周期钩子系统

开源内核与闭源商业模块解耦的核心设计。
定义 LangGraph 仿真全流程的可扩展钩子点位，
支持同步/异步回调、优先级调度、异常隔离。
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Union

from presim_core.engine.state import SimulationState

logger = logging.getLogger(__name__)


# =============================================================================
# 钩子点位常量 - 覆盖 LangGraph 仿真全流程
# =============================================================================

HOOK_BEFORE_SIMULATION_START = "before_simulation_start"
"""仿真启动前。用途：修改初始状态、校验配置、初始化闭源模块。"""

HOOK_BEFORE_STEP_START = "before_step_start"
"""每一轮仿真步骤开始前。用途：修改环境数据、干预状态、风险前置检测。"""

HOOK_BEFORE_AGENT_ACT = "before_agent_act"
"""每个智能体执行行动前。用途：介入感知/思考过程，高保真行为建模、幻觉控制。"""

HOOK_AFTER_AGENT_ACT = "after_agent_act"
"""每个智能体执行行动后。用途：校验行动结果、更新记忆、记录行为数据。"""

HOOK_AFTER_STEP_END = "after_step_end"
"""每一轮仿真步骤结束后。用途：状态校验、风险预警、因果链路分析、长时序稳定性控制。"""

HOOK_BEFORE_SIMULATION_END = "before_simulation_end"
"""仿真结束前。用途：结果校验、补充分析数据、风险汇总。"""

HOOK_ON_SIMULATION_ERROR = "on_simulation_error"
"""仿真出现异常时。用途：异常处理、日志上报、故障恢复。"""

# 兼容旧版 registry 的钩子名称别名
HOOK_BEFORE_SIMULATION = HOOK_BEFORE_SIMULATION_START
HOOK_AFTER_STEP = HOOK_AFTER_STEP_END
HOOK_BEFORE_SIMULATION_END_ALIAS = HOOK_BEFORE_SIMULATION_END  # 原 after_simulation 语义
HOOK_ON_ERROR = HOOK_ON_SIMULATION_ERROR

# 所有预定义钩子点位（便于校验与遍历）
ALL_HOOK_POINTS: tuple[str, ...] = (
    HOOK_BEFORE_SIMULATION_START,
    HOOK_BEFORE_STEP_START,
    HOOK_BEFORE_AGENT_ACT,
    HOOK_AFTER_AGENT_ACT,
    HOOK_AFTER_STEP_END,
    HOOK_BEFORE_SIMULATION_END,
    HOOK_ON_SIMULATION_ERROR,
)


# =============================================================================
# 钩子入参/出参规范
# =============================================================================


@dataclass
class HookContext:
    """
    钩子上下文 - 传递仿真环境与扩展信息

    Attributes:
        state: 当前仿真状态
        step: 当前步数（步骤相关钩子）
        agent_name: 智能体名称（智能体相关钩子）
        extra: 扩展数据，供闭源模块传递自定义信息
    """

    state: SimulationState
    step: int = 0
    agent_name: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HookResult:
    """
    钩子返回值 - 用于修改状态或控制流程

    钩子回调可返回 None（无操作）或 HookResult。
    多个钩子的 state_updates 将按执行顺序合并；
    任一钩子返回 stop=True 将请求终止仿真流程。

    Attributes:
        state_updates: 要合并到仿真状态的字段更新（dict）
        stop: 是否请求终止仿真
        error: 错误信息（仅记录，不抛异常）
    """

    state_updates: Optional[Dict[str, Any]] = None
    stop: bool = False
    error: Optional[str] = None

    def merge_into(self, target: Dict[str, Any]) -> None:
        """将 state_updates 合并到目标字典"""
        if self.state_updates:
            target.update(self.state_updates)


# 钩子回调类型：同步返回 None | HookResult | dict
HookCallbackReturn = Optional[Union[HookResult, Dict[str, Any]]]
# 支持同步与异步回调
HookCallback = Union[
    Callable[..., HookCallbackReturn],
    Callable[..., Any],  # 异步回调
]


# =============================================================================
# HookManager - 钩子注册、注销、执行调度
# =============================================================================


@dataclass
class _HookEntry:
    """内部：单个钩子注册项"""

    callback: HookCallback
    priority: int


class HookManager:
    """
    钩子管理器 - 负责钩子的注册、注销、执行调度

    支持同一钩子点位注册多个回调，按优先级顺序执行；
    支持同步与异步回调；单钩子失败不影响整体流程。
    线程安全，支持多场景的钩子隔离（通过实例隔离）。
    """

    def __init__(self, scope: Optional[str] = None) -> None:
        """
        初始化钩子管理器

        Args:
            scope: 可选作用域标识，用于多场景隔离（如不同仿真实例）
        """
        self._scope = scope or "default"
        self._hooks: Dict[str, List[_HookEntry]] = {}
        self._lock = threading.RLock()

    def register_hook(
        self,
        hook_point: str,
        callback: HookCallback,
        priority: int = 10,
    ) -> None:
        """
        注册钩子回调

        优先级数字越小，执行越靠前。同优先级按注册顺序执行。

        Args:
            hook_point: 钩子点位名称，建议使用预定义常量
            callback: 回调函数，签名为 (ctx: HookContext, **kwargs) -> HookResult | dict | None
            priority: 优先级，默认 10

        Example:
            >>> def my_hook(ctx: HookContext) -> None:
            ...     ctx.state.config["validated"] = True
            >>> manager.register_hook(HOOK_BEFORE_SIMULATION_START, my_hook, priority=5)
        """
        with self._lock:
            if hook_point not in self._hooks:
                self._hooks[hook_point] = []
            entry = _HookEntry(callback=callback, priority=priority)
            self._hooks[hook_point].append(entry)
            self._hooks[hook_point].sort(key=lambda e: e.priority)
            logger.debug(
                "注册钩子: %s @ %s (priority=%d, scope=%s)",
                hook_point,
                getattr(callback, "__name__", callback),
                priority,
                self._scope,
            )

    def unregister_hook(self, hook_point: str, callback: HookCallback) -> bool:
        """
        注销指定钩子

        Args:
            hook_point: 钩子点位名称
            callback: 要移除的回调函数（需为同一引用）

        Returns:
            是否成功注销
        """
        with self._lock:
            if hook_point not in self._hooks:
                return False
            original_len = len(self._hooks[hook_point])
            self._hooks[hook_point] = [e for e in self._hooks[hook_point] if e.callback is not callback]
            removed = len(self._hooks[hook_point]) < original_len
            if not self._hooks[hook_point]:
                del self._hooks[hook_point]
            return removed

    def clear_hooks(self, hook_point: Optional[str] = None) -> None:
        """
        清空钩子

        Args:
            hook_point: 指定点位则只清空该点位；None 则清空所有
        """
        with self._lock:
            if hook_point is None:
                self._hooks.clear()
                logger.debug("清空所有钩子 (scope=%s)", self._scope)
            elif hook_point in self._hooks:
                del self._hooks[hook_point]
                logger.debug("清空钩子点位: %s (scope=%s)", hook_point, self._scope)

    def execute_hooks(
        self,
        hook_point: str,
        ctx: HookContext,
        **kwargs: Any,
    ) -> HookResult:
        """
        同步执行指定点位的所有钩子回调

        按优先级顺序执行；同步回调直接调用，异步回调通过 asyncio.run 执行。
        单个回调失败仅记录日志，不中断后续回调；最终合并所有 state_updates，
        任一 stop=True 则结果中 stop 为 True。

        Args:
            hook_point: 钩子点位名称
            ctx: 钩子上下文
            **kwargs: 额外传递给回调的参数

        Returns:
            合并后的 HookResult，供调用方应用状态更新或判断是否终止
        """
        entries = self._get_entries(hook_point)
        if not entries:
            return HookResult()

        merged = HookResult(state_updates={})
        should_stop = False

        for entry in entries:
            try:
                result = self._run_callback(entry.callback, ctx, **kwargs)
                if result is not None:
                    if isinstance(result, dict):
                        result = HookResult(state_updates=result)
                    if result.state_updates:
                        if merged.state_updates is None:
                            merged.state_updates = dict(result.state_updates)
                        else:
                            merged.state_updates.update(result.state_updates)
                    if result.stop:
                        should_stop = True
                    if result.error:
                        logger.warning("钩子 %s 返回错误: %s", hook_point, result.error)
            except Exception as e:
                logger.exception(
                    "钩子执行失败 [%s] %s: %s",
                    hook_point,
                    getattr(entry.callback, "__name__", entry.callback),
                    e,
                )
                # 不抛出，继续执行后续钩子

        merged.stop = should_stop
        return merged

    async def execute_hooks_async(
        self,
        hook_point: str,
        ctx: HookContext,
        **kwargs: Any,
    ) -> HookResult:
        """
        异步执行指定点位的所有钩子回调

        适用于仿真引擎在 async 上下文中调用。
        同步回调在线程池中执行，异步回调直接 await。

        Args:
            hook_point: 钩子点位名称
            ctx: 钩子上下文
            **kwargs: 额外参数

        Returns:
            合并后的 HookResult
        """
        entries = self._get_entries(hook_point)
        if not entries:
            return HookResult()

        merged = HookResult(state_updates={})
        should_stop = False

        for entry in entries:
            try:
                result = await self._run_callback_async(entry.callback, ctx, **kwargs)
                if result is not None:
                    if isinstance(result, dict):
                        result = HookResult(state_updates=result)
                    if result.state_updates:
                        if merged.state_updates is None:
                            merged.state_updates = dict(result.state_updates)
                        else:
                            merged.state_updates.update(result.state_updates)
                    if result.stop:
                        should_stop = True
                    if result.error:
                        logger.warning("钩子 %s 返回错误: %s", hook_point, result.error)
            except Exception as e:
                logger.exception(
                    "钩子执行失败 [%s] %s: %s",
                    hook_point,
                    getattr(entry.callback, "__name__", entry.callback),
                    e,
                )

        merged.stop = should_stop
        return merged

    def _get_entries(self, hook_point: str) -> List[_HookEntry]:
        """获取排序后的钩子列表（线程安全）"""
        with self._lock:
            return list(self._hooks.get(hook_point, []))

    def _run_callback(
        self,
        callback: HookCallback,
        ctx: HookContext,
        **kwargs: Any,
    ) -> HookCallbackReturn:
        """执行单个回调（同步或异步）"""
        if asyncio.iscoroutinefunction(callback):
            return asyncio.run(self._run_callback_async(callback, ctx, **kwargs))
        sig = inspect.signature(callback)
        param_names = set(sig.parameters.keys())
        # 只传递回调声明的参数，避免 unexpected keyword argument
        filtered = {k: v for k, v in kwargs.items() if k in param_names}
        if param_names and list(param_names)[0] in ("ctx", "context"):
            return callback(ctx, **filtered)
        # 兼容旧式 (state, **kwargs)
        return callback(ctx.state, **filtered)

    async def _run_callback_async(
        self,
        callback: HookCallback,
        ctx: HookContext,
        **kwargs: Any,
    ) -> HookCallbackReturn:
        """异步执行单个回调"""
        param_names = set(inspect.signature(callback).parameters.keys())
        filtered = {k: v for k, v in kwargs.items() if k in param_names}
        if asyncio.iscoroutinefunction(callback):
            if param_names and list(param_names)[0] in ("ctx", "context"):
                return await callback(ctx, **filtered)
            return await callback(ctx.state, **filtered)
        # 同步回调在线程池执行
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self._run_sync_only(callback, ctx, **kwargs),
        )

    def _run_sync_only(
        self,
        callback: HookCallback,
        ctx: HookContext,
        **kwargs: Any,
    ) -> HookCallbackReturn:
        """仅执行同步回调（不处理协程）"""
        param_names = set(inspect.signature(callback).parameters.keys())
        filtered = {k: v for k, v in kwargs.items() if k in param_names}
        if param_names and list(param_names)[0] in ("ctx", "context"):
            return callback(ctx, **filtered)
        return callback(ctx.state, **filtered)

    def list_hooks(self, hook_point: Optional[str] = None) -> Dict[str, int]:
        """
        列出已注册的钩子数量

        Args:
            hook_point: 指定点位则只返回该点位数量；None 返回所有

        Returns:
            {hook_point: count}
        """
        with self._lock:
            if hook_point is not None:
                return {hook_point: len(self._hooks.get(hook_point, []))}
            return {k: len(v) for k, v in self._hooks.items()}


# =============================================================================
# 全局默认实例 & 便捷桥接（兼容 registry）
# =============================================================================

_default_manager: Optional[HookManager] = None
_default_manager_lock = threading.Lock()


def get_hook_manager(scope: Optional[str] = None) -> HookManager:
    """
    获取钩子管理器实例

    Args:
        scope: 作用域，None 时返回默认单例

    Returns:
        HookManager 实例
    """
    global _default_manager
    if scope is None:
        with _default_manager_lock:
            if _default_manager is None:
                _default_manager = HookManager(scope="default")
            return _default_manager
    return HookManager(scope=scope)


class EngineHooks:
    """
    引擎生命周期钩子调度器（兼容层）

    委托给 HookManager 执行，提供与 registry 模块一致的调用接口。
    仿真引擎在对应节点调用此类方法即可，无需关心闭源模块实现。
    """

    def __init__(self, manager: Optional[HookManager] = None) -> None:
        """
        初始化

        Args:
            manager: 指定 HookManager，None 时使用默认单例
        """
        self._manager = manager or get_hook_manager()

    def before_simulation_start(self, state: SimulationState) -> HookResult:
        """仿真启动前"""
        ctx = HookContext(state=state)
        return self._manager.execute_hooks(HOOK_BEFORE_SIMULATION_START, ctx)

    def before_step_start(self, state: SimulationState, step: int) -> HookResult:
        """每步开始前"""
        ctx = HookContext(state=state, step=step)
        return self._manager.execute_hooks(HOOK_BEFORE_STEP_START, ctx)

    def before_agent_act(
        self,
        state: SimulationState,
        step: int,
        agent_name: str,
        **extra: Any,
    ) -> HookResult:
        """智能体行动前"""
        ctx = HookContext(state=state, step=step, agent_name=agent_name, extra=extra)
        return self._manager.execute_hooks(HOOK_BEFORE_AGENT_ACT, ctx)

    def after_agent_act(
        self,
        state: SimulationState,
        step: int,
        agent_name: str,
        action_result: Any,
        **extra: Any,
    ) -> HookResult:
        """智能体行动后"""
        ctx = HookContext(state=state, step=step, agent_name=agent_name, extra={"action_result": action_result, **extra})
        return self._manager.execute_hooks(HOOK_AFTER_AGENT_ACT, ctx)

    def after_step_end(self, state: SimulationState, step: int) -> HookResult:
        """每步结束后"""
        ctx = HookContext(state=state, step=step)
        return self._manager.execute_hooks(HOOK_AFTER_STEP_END, ctx)

    def before_simulation_end(self, state: SimulationState) -> HookResult:
        """仿真结束前"""
        ctx = HookContext(state=state, step=state.step)
        return self._manager.execute_hooks(HOOK_BEFORE_SIMULATION_END, ctx)

    def on_simulation_error(self, state: SimulationState, error: Exception) -> HookResult:
        """仿真异常时"""
        ctx = HookContext(state=state, extra={"error": error})
        return self._manager.execute_hooks(HOOK_ON_SIMULATION_ERROR, ctx)


# =============================================================================
# 工具函数 - 将 HookResult 应用到 SimulationState
# =============================================================================


def apply_hook_result_to_state(state: SimulationState, result: HookResult) -> SimulationState:
    """
    将 HookResult 的 state_updates 应用到仿真状态

    用于引擎在钩子执行后合并状态更新。仅更新 SimulationState 已有的字段，
    扩展字段通过 context 或 extra 传递。

    Args:
        state: 当前仿真状态
        result: 钩子返回结果

    Returns:
        更新后的新状态实例（Pydantic 不可变则返回 copy）
    """
    if not result or not result.state_updates:
        return state
    try:
        return state.model_copy(update=result.state_updates)
    except Exception:
        # 非 Pydantic 或部分字段不可更新时，逐字段 setattr
        for k, v in result.state_updates.items():
            if hasattr(state, k):
                setattr(state, k, v)
        return state


# =============================================================================
# 统一导出
# =============================================================================

__all__ = [
    # 钩子点位常量
    "HOOK_BEFORE_SIMULATION_START",
    "HOOK_BEFORE_STEP_START",
    "HOOK_BEFORE_AGENT_ACT",
    "HOOK_AFTER_AGENT_ACT",
    "HOOK_AFTER_STEP_END",
    "HOOK_BEFORE_SIMULATION_END",
    "HOOK_ON_SIMULATION_ERROR",
    "HOOK_BEFORE_SIMULATION",
    "HOOK_AFTER_STEP",
    "HOOK_ON_ERROR",
    "ALL_HOOK_POINTS",
    # 数据结构
    "HookContext",
    "HookResult",
    # 核心类
    "HookManager",
    "EngineHooks",
    # 便捷函数
    "get_hook_manager",
    "apply_hook_result_to_state",
]
