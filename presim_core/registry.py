"""
扩展注册表 - 开源内核与闭源商业模块解耦的核心组件

微内核架构的核心，负责:
- 钩子管理（对接 HookManager）
- 自定义智能体注册与获取
- 扩展模块生命周期管理
- 自定义组件（解析器、环境更新器、结果处理器）注册
- 自动发现与加载 presim 扩展包

闭源模块只需通过注册表标准接口注册，即可实现能力注入与替换，
完美符合依赖倒置原则。
"""

from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol, Type, Union

logger = logging.getLogger(__name__)

# 扩展发现相关常量
ENTRY_POINT_GROUP = "presim.extensions"
"""
setuptools 入口点组名。扩展包在 setup.py/pyproject.toml 中声明:

  entry_points={
      "presim.extensions": [
          "presim-matrix-pro = presim_matrix_pro:register",
      ],
  },

register 函数签名为 def register(registry: ExtensionRegistry) -> None
"""

ENV_EXTENSIONS = "PRESIM_EXTENSIONS"
"""环境变量：逗号分隔的扩展名列表，'all' 表示加载全部，空则仅加载显式配置"""

ENV_EXTENSIONS_DISABLED = "PRESIM_EXTENSIONS_DISABLED"
"""环境变量：逗号分隔的禁用扩展名"""

CONFIG_EXTENSIONS_KEY = "extensions"
"""配置文件中扩展列表的键名"""


# =============================================================================
# 扩展模块协议 - 可选生命周期接口
# =============================================================================


class ExtensionModule(Protocol):
    """
    扩展模块协议 - 可选实现的生命周期方法

    扩展模块可以是任意对象，若实现以下方法则会在对应时机被调用。
    """

    def on_init(self, registry: "ExtensionRegistry") -> None:
        """扩展初始化时调用"""
        ...

    def on_start(self, registry: "ExtensionRegistry") -> None:
        """扩展启动时调用"""
        ...

    def on_stop(self, registry: "ExtensionRegistry") -> None:
        """扩展关闭时调用"""
        ...


@dataclass
class _ExtensionEntry:
    """内部：扩展模块注册项"""

    name: str
    module: Any
    enabled: bool = True
    loaded: bool = False
    error: Optional[str] = None


@dataclass
class _HookRegistration:
    """内部：批量钩子注册项"""

    hook_point: str
    callback: Callable
    priority: int = 10


# =============================================================================
# ExtensionRegistry 单例
# =============================================================================


class ExtensionRegistry:
    """
    扩展注册表 - 全局单例

    负责钩子管理、智能体注册、扩展模块管理、自定义组件注册。
    保证整个项目生命周期内只有一个实例。
    """

    _instance: Optional["ExtensionRegistry"] = None
    _lock = threading.RLock()

    def __new__(cls) -> "ExtensionRegistry":
        """单例：全局唯一实例"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """初始化（单例下仅执行一次）"""
        if hasattr(self, "_initialized") and self._initialized:
            return

        self._initialized = True
        self._agent_classes: Dict[str, Type[Any]] = {}
        self._extensions: Dict[str, _ExtensionEntry] = {}
        self._plugins: Dict[str, Any] = {}  # 通用插件存储（兼容旧 API）
        self._parsers: Dict[str, Any] = {}
        self._env_updaters: Dict[str, Any] = {}
        self._result_processors: Dict[str, Any] = {}
        self._registry_lock = threading.RLock()

        # 延迟加载 HookManager，避免循环导入
        self._hook_manager: Optional[Any] = None

    def _get_hook_manager(self) -> Any:
        """获取 HookManager（延迟导入）"""
        if self._hook_manager is None:
            from presim_core.engine.hooks import get_hook_manager

            self._hook_manager = get_hook_manager()
        return self._hook_manager

    # -------------------------------------------------------------------------
    # 智能体注册与管理
    # -------------------------------------------------------------------------

    def register_agent_class(self, agent_type: str, agent_class: Type[Any]) -> None:
        """
        注册自定义智能体类

        闭源的高保真智能体通过此方法注册，实现与开源默认智能体的无缝替换。

        Args:
            agent_type: 智能体类型标识，如 "consumer"、"decision"
            agent_class: 继承 BaseAgent 的智能体类

        Raises:
            TypeError: agent_class 非类类型时
        """
        if not isinstance(agent_class, type):
            raise TypeError(f"agent_class 必须为类类型，实际: {type(agent_class)}")
        with self._registry_lock:
            self._agent_classes[agent_type] = agent_class
            logger.info("注册智能体类型: %s -> %s", agent_type, getattr(agent_class, "__name__", agent_class))

    def get_agent_class(self, agent_type: str) -> Type[Any]:
        """
        获取智能体类

        优先返回注册的自定义闭源智能体，若无则返回开源默认基础智能体。

        Args:
            agent_type: 智能体类型标识

        Returns:
            智能体类（未实例化）

        Raises:
            KeyError: 无注册且无默认实现时
        """
        with self._registry_lock:
            if agent_type in self._agent_classes:
                return self._agent_classes[agent_type]

        # 回退到开源默认智能体
        defaults: Dict[str, Type[Any]] = {
            "consumer": self._load_default_agent("ConsumerAgent"),
            "decision": self._load_default_agent("DecisionAgent"),
        }
        if agent_type in defaults:
            return defaults[agent_type]
        raise KeyError(f"未找到智能体类型 '{agent_type}'，且无默认实现。已注册: {self.list_agent_types()}")

    def _load_default_agent(self, class_name: str) -> Type[Any]:
        """延迟加载默认智能体类"""
        from presim_core.agents.default_agents import ConsumerAgent, DecisionAgent

        return {"ConsumerAgent": ConsumerAgent, "DecisionAgent": DecisionAgent}[class_name]

    def list_agent_types(self) -> List[str]:
        """列出所有已注册的智能体类型（含默认）"""
        with self._registry_lock:
            registered = set(self._agent_classes.keys())
        defaults = {"consumer", "decision"}
        return sorted(registered | defaults)

    def create_agent(self, agent_type: str, **kwargs: Any) -> Any:
        """
        创建智能体实例

        Args:
            agent_type: 智能体类型
            **kwargs: 传递给智能体构造函数的参数

        Returns:
            智能体实例
        """
        cls = self.get_agent_class(agent_type)
        return cls(**kwargs)

    # -------------------------------------------------------------------------
    # 钩子系统集成
    # -------------------------------------------------------------------------

    def register_hook(
        self,
        hook_point: str,
        callback: Callable[..., Any],
        priority: int = 10,
    ) -> None:
        """
        注册生命周期钩子（委托给 HookManager）

        Args:
            hook_point: 钩子点位名称，使用 presim_core.engine.hooks 中的常量
            callback: 回调函数，(ctx: HookContext, **kwargs) -> HookResult | dict | None
            priority: 优先级，数字越小越先执行
        """
        try:
            self._get_hook_manager().register_hook(hook_point, callback, priority=priority)
        except Exception as e:
            logger.exception("注册钩子失败 [%s]: %s", hook_point, e)
            raise

    def register_hooks_batch(self, registrations: List[Dict[str, Any]]) -> None:
        """
        批量注册多个钩子

        Args:
            registrations: 列表，每项为 {"hook_point": str, "callback": Callable, "priority": int(可选)}
        """
        for r in registrations:
            hook_point = r.get("hook_point")
            callback = r.get("callback")
            if not hook_point or callback is None:
                logger.warning("跳过无效钩子注册: %s", r)
                continue
            priority = r.get("priority", 10)
            try:
                self.register_hook(hook_point, callback, priority=priority)
            except Exception as e:
                logger.warning("批量注册钩子失败 [%s]: %s", hook_point, e)

    def execute_hooks(
        self,
        hook_point: str,
        ctx: Any,
        **kwargs: Any,
    ) -> Any:
        """
        执行指定点位的所有钩子

        Args:
            hook_point: 钩子点位名称
            ctx: HookContext 实例
            **kwargs: 额外参数

        Returns:
            HookResult
        """
        return self._get_hook_manager().execute_hooks(hook_point, ctx, **kwargs)

    def list_hooks(self, hook_point: Optional[str] = None) -> Dict[str, int]:
        """列出已注册钩子数量"""
        return self._get_hook_manager().list_hooks(hook_point)

    def emit_hook(self, hook_name: str, *args: Any, **kwargs: Any) -> None:
        """
        触发指定名称的所有钩子（兼容旧用法，仅通知不返回）

        新代码建议使用 EngineHooks 或 execute_hooks 以获取返回值。
        """
        from presim_core.engine.hooks import HookContext
        from presim_core.engine.state import SimulationState

        manager = self._get_hook_manager()
        state = kwargs.get("state") or (args[0] if args and isinstance(args[0], SimulationState) else None)
        if state is not None:
            ctx = HookContext(state=state, step=kwargs.get("step", 0), extra=dict(kwargs))
            manager.execute_hooks(hook_name, ctx, **kwargs)

    # -------------------------------------------------------------------------
    # 扩展模块管理
    # -------------------------------------------------------------------------

    def register_extension(
        self,
        extension_name: str,
        extension_module: Any,
        *,
        enabled: bool = True,
        init_now: bool = True,
    ) -> None:
        """
        注册扩展模块

        支持扩展的初始化、启动、关闭生命周期。启用/禁用不影响内核稳定运行。

        Args:
            extension_name: 扩展唯一标识
            extension_module: 扩展模块或对象，可实现 on_init/on_start/on_stop
            enabled: 是否启用
            init_now: 是否立即调用 on_init
        """
        with self._registry_lock:
            entry = _ExtensionEntry(
                name=extension_name,
                module=extension_module,
                enabled=enabled,
            )
            self._extensions[extension_name] = entry

        if init_now and enabled:
            self._call_extension_lifecycle(extension_name, "on_init")

    def get_extension(self, extension_name: str) -> Optional[Any]:
        """获取扩展模块，未找到或已禁用返回 None"""
        with self._registry_lock:
            entry = self._extensions.get(extension_name)
            if entry and entry.enabled:
                return entry.module
        return None

    def enable_extension(self, extension_name: str) -> bool:
        """启用扩展"""
        with self._registry_lock:
            if extension_name in self._extensions:
                self._extensions[extension_name].enabled = True
                return True
        return False

    def disable_extension(self, extension_name: str) -> bool:
        """禁用扩展"""
        with self._registry_lock:
            if extension_name in self._extensions:
                self._extensions[extension_name].enabled = False
                return True
        return False

    def start_extension(self, extension_name: str) -> None:
        """启动扩展（调用 on_start）"""
        self._call_extension_lifecycle(extension_name, "on_start")

    def stop_extension(self, extension_name: str) -> None:
        """停止扩展（调用 on_stop）"""
        self._call_extension_lifecycle(extension_name, "on_stop")

    def _call_extension_lifecycle(self, extension_name: str, method: str) -> None:
        """安全调用扩展生命周期方法"""
        with self._registry_lock:
            entry = self._extensions.get(extension_name)
            if not entry or not entry.enabled:
                return
            mod = entry.module

        if not hasattr(mod, method):
            return
        fn = getattr(mod, method)
        try:
            fn(self)
        except Exception as e:
            logger.exception("扩展 %s.%s 执行失败: %s", extension_name, method, e)
            with self._registry_lock:
                if extension_name in self._extensions:
                    self._extensions[extension_name].error = str(e)

    def register_plugin(self, name: str, plugin: Any) -> None:
        """注册通用插件（兼容旧 API）"""
        with self._registry_lock:
            self._plugins[name] = plugin

    def get_plugin(self, name: str) -> Optional[Any]:
        """获取插件（兼容旧 API）"""
        with self._registry_lock:
            return self._plugins.get(name)

    def list_plugins(self) -> List[str]:
        """列出插件名称（兼容旧 API）"""
        with self._registry_lock:
            return list(self._plugins.keys())

    def list_extensions(self) -> List[Dict[str, Any]]:
        """列出所有扩展及其状态"""
        with self._registry_lock:
            return [
                {
                    "name": name,
                    "enabled": e.enabled,
                    "loaded": e.loaded,
                    "error": e.error,
                }
                for name, e in self._extensions.items()
            ]

    # -------------------------------------------------------------------------
    # 自定义组件注册
    # -------------------------------------------------------------------------

    def register_parser(self, name: str, parser: Any) -> None:
        """
        注册自定义结果解析器

        闭源模块可替换/增强内核的 ResultParser 能力。

        Args:
            name: 解析器标识
            parser: 解析器实例，需实现 parse_timeline 等接口
        """
        with self._registry_lock:
            self._parsers[name] = parser

    def get_parser(self, name: Optional[str] = None) -> Any:
        """
        获取解析器

        Args:
            name: 解析器名称，None 时返回默认 ResultParser

        Returns:
            解析器实例
        """
        with self._registry_lock:
            if name and name in self._parsers:
                return self._parsers[name]

        from presim_core.parser.result_parser import ResultParser

        return ResultParser()

    def register_env_updater(self, name: str, updater: Any) -> None:
        """注册环境更新器（预留）"""
        with self._registry_lock:
            self._env_updaters[name] = updater

    def get_env_updater(self, name: Optional[str] = None) -> Optional[Any]:
        """获取环境更新器"""
        with self._registry_lock:
            if name and name in self._env_updaters:
                return self._env_updaters[name]
            if self._env_updaters:
                return next(iter(self._env_updaters.values()))
        return None

    def register_result_processor(self, name: str, processor: Any) -> None:
        """注册结果处理器（预留）"""
        with self._registry_lock:
            self._result_processors[name] = processor

    def get_result_processor(self, name: Optional[str] = None) -> Optional[Any]:
        """获取结果处理器"""
        with self._registry_lock:
            if name and name in self._result_processors:
                return self._result_processors[name]
            if self._result_processors:
                return next(iter(self._result_processors.values()))
        return None

    # -------------------------------------------------------------------------
    # 自动发现与加载
    # -------------------------------------------------------------------------

    def discover_and_load_extensions(
        self,
        *,
        config_path: Optional[Union[str, Path]] = None,
        extra_extensions: Optional[List[str]] = None,
    ) -> int:
        """
        自动发现并加载 presim 扩展包

        扫描环境中安装的 presim 扩展（通过 entry point presim.extensions），
        以及配置文件、环境变量指定的扩展，在系统启动时自动加载。

        Args:
            config_path: 配置文件路径，支持 YAML，可含 extensions: [name1, name2]
            extra_extensions: 额外要加载的扩展名列表

        Returns:
            成功加载的扩展数量
        """
        to_load = self._resolve_extensions_to_load(config_path, extra_extensions)
        if not to_load:
            return 0

        loaded_count = 0
        for ext_name in to_load:
            try:
                self._load_extension_by_name(ext_name)
                loaded_count += 1
            except Exception as e:
                logger.warning("加载扩展 %s 失败: %s", ext_name, e)

        return loaded_count

    def _resolve_extensions_to_load(
        self,
        config_path: Optional[Union[str, Path]] = None,
        extra_extensions: Optional[List[str]] = None,
    ) -> List[str]:
        """解析要加载的扩展列表"""
        disabled = set()
        env_disabled = os.environ.get(ENV_EXTENSIONS_DISABLED, "").strip()
        if env_disabled:
            disabled.update(s.strip() for s in env_disabled.split(",") if s.strip())

        # 1. 环境变量
        env_ext = os.environ.get(ENV_EXTENSIONS, "").strip()
        if env_ext.lower() == "all":
            return [n for n in self._discover_extension_names() if n not in disabled]
        if env_ext:
            from_env = [s.strip() for s in env_ext.split(",") if s.strip()]
            return [n for n in from_env if n not in disabled]

        # 2. 配置文件
        from_config: List[str] = []
        if config_path:
            from_config = self._load_extensions_from_config(config_path)
        if from_config:
            return [n for n in from_config if n not in disabled]

        # 3. 额外指定
        if extra_extensions:
            return [n for n in extra_extensions if n not in disabled]

        # 4. 默认：发现全部并加载
        return [n for n in self._discover_extension_names() if n not in disabled]

    def _discover_extension_names(self) -> List[str]:
        """通过 entry points 发现扩展名"""
        try:
            from importlib.metadata import entry_points

            eps = entry_points(group=ENTRY_POINT_GROUP)
            return [ep.name for ep in eps]
        except Exception as e:
            logger.debug("entry_points 发现扩展失败: %s", e)
            return []

    def _load_extension_by_name(self, extension_name: str) -> None:
        """按名称加载扩展（通过 entry point 或直接导入）"""
        import importlib

        try:
            from importlib.metadata import entry_points

            eps = entry_points(group=ENTRY_POINT_GROUP)
            ep = next((e for e in eps if e.name == extension_name), None)
            if ep is None:
                # 尝试直接导入：presim_matrix_pro 等
                mod_name = extension_name.replace("-", "_")
                try:
                    mod = importlib.import_module(mod_name)
                    if hasattr(mod, "register"):
                        reg = getattr(mod, "register")
                        if callable(reg):
                            try:
                                reg(self)
                            except TypeError:
                                reg()
                    self.register_extension(extension_name, mod, init_now=True)
                    with self._registry_lock:
                        if extension_name in self._extensions:
                            self._extensions[extension_name].loaded = True
                    return
                except ImportError:
                    pass
                raise ValueError(f"未找到扩展: {extension_name}")

            register_fn = ep.load()
            if not callable(register_fn):
                raise TypeError(f"扩展 {extension_name} 的注册对象不可调用")

            # 约定：register_fn(registry) 或 register_fn()
            try:
                register_fn(self)
            except TypeError:
                register_fn()

            # 使用 entry point 所在模块作为扩展模块，支持生命周期
            mod_name = getattr(ep, "module", ep.value.split(":")[0] if ":" in str(ep.value) else None)
            ext_module = register_fn
            if mod_name:
                try:
                    ext_module = importlib.import_module(mod_name)
                except Exception:
                    pass

            self.register_extension(extension_name, ext_module, init_now=False)
            with self._registry_lock:
                if extension_name in self._extensions:
                    self._extensions[extension_name].loaded = True

        except Exception as e:
            logger.exception("加载扩展 %s 失败: %s", extension_name, e)
            with self._registry_lock:
                if extension_name in self._extensions:
                    self._extensions[extension_name].error = str(e)
            raise

    def _load_extensions_from_config(self, config_path: Union[str, Path]) -> List[str]:
        """从配置文件读取扩展列表"""
        path = Path(config_path)
        if not path.exists():
            return []
        try:
            import yaml

            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            return data.get(CONFIG_EXTENSIONS_KEY, [])
        except Exception as e:
            logger.warning("读取扩展配置失败 %s: %s", config_path, e)
            return []


# =============================================================================
# 全局单例访问
# =============================================================================

_extension_registry: Optional[ExtensionRegistry] = None
_extension_registry_lock = threading.Lock()


def get_registry() -> ExtensionRegistry:
    """获取扩展注册表单例"""
    global _extension_registry
    if _extension_registry is None:
        with _extension_registry_lock:
            if _extension_registry is None:
                _extension_registry = ExtensionRegistry()
    return _extension_registry


# 兼容旧 API
Registry = ExtensionRegistry


# =============================================================================
# 统一导出
# =============================================================================

__all__ = [
    "ExtensionRegistry",
    "ExtensionModule",
    "get_registry",
    "Registry",
    "ENTRY_POINT_GROUP",
    "ENV_EXTENSIONS",
    "ENV_EXTENSIONS_DISABLED",
]
