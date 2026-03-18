# 商业/社区插件开发指南

## 概述

预演沙盘通过 **扩展注册表 (ExtensionRegistry)** 支持闭源商业模块与社区插件的安全接入，无需修改内核代码。

## 注册流程

### 1. 获取注册表

```python
from presim_core import get_registry, registry

registry = get_registry()  # 或直接使用 presim_core.registry
```

### 2. 注册扩展模块

```python
class MyExtension:
    def on_init(self, registry):
        registry.register_agent_class("consumer", MyConsumerAgent)

registry.register_extension("my_business", MyExtension(), init_now=True)
```

### 3. 注册生命周期钩子

```python
from presim_core.engine.hooks import HOOK_BEFORE_SIMULATION_START, HookContext, HookResult

def my_before_hook(ctx: HookContext) -> HookResult:
    # 仿真开始前的自定义逻辑，可返回状态更新
    return HookResult(state_updates={"config": {"validated": True}})

registry.register_hook(HOOK_BEFORE_SIMULATION_START, my_before_hook, priority=5)
```

## 预定义钩子点位

| 钩子名 | 触发时机 | 用途 |
|--------|----------|------|
| before_simulation_start | 仿真启动前 | 修改初始状态、校验配置、初始化闭源模块 |
| before_step_start | 每步开始前 | 修改环境数据、干预状态、风险前置检测 |
| before_agent_act | 智能体行动前 | 介入感知/思考，高保真行为建模、幻觉控制 |
| after_agent_act | 智能体行动后 | 校验行动结果、更新记忆、记录行为数据 |
| after_step_end | 每步结束后 | 状态校验、风险预警、因果链路分析 |
| before_simulation_end | 仿真结束前 | 结果校验、补充分析数据、风险汇总 |
| on_simulation_error | 仿真异常时 | 异常处理、日志上报、故障恢复 |

推荐使用 `HookManager` 直接注册，支持优先级与返回值：

```python
from presim_core.engine.hooks import get_hook_manager, HOOK_BEFORE_SIMULATION_START, HookContext, HookResult

def my_hook(ctx: HookContext) -> HookResult:
    ctx.state.config["validated"] = True
    return HookResult(state_updates={"config": ctx.state.config})

get_hook_manager().register_hook(HOOK_BEFORE_SIMULATION_START, my_hook, priority=5)
```

## 扩展 Agent

继承 `BaseAgent`，实现 `perceive`、`think`、`act`，通过注册表注册：

```python
registry.register_agent_class("consumer", MyConsumerAgent)
# 引擎调用 get_agent_class("consumer") 时将返回 MyConsumerAgent，实现无缝替换
```

## 自动发现扩展

扩展包在 setup.py 中声明 entry point 后，内核启动时自动加载：

```python
# setup.py
entry_points={
    "presim.extensions": [
        "presim-matrix-pro = presim_matrix_pro:register",
    ],
}
```

环境变量 `PRESIM_EXTENSIONS` 可配置要加载的扩展（逗号分隔），`all` 表示加载全部。

## 扩展 LLM 适配器

继承 `BaseLLMAdapter`，实现 `sync_chat`、`stream_chat`、`async_chat`，通过 `register_adapter` 注册到工厂。

## 注意事项

- 闭源模块不得修改 `presim_core` 内任何文件
- 所有扩展必须通过 `Registry` 进行
- 钩子回调应避免阻塞主流程
