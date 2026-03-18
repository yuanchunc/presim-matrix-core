# 预演沙盘 PreSim Matrix - 架构说明

## 概述

预演沙盘采用 **微内核 + 插件注册表** 架构，严格实现开源内核与闭源商业模块的解耦。

## 核心目录结构

```
presim-matrix-core/
├── presim_core/       # 核心代码库 - 100% 开源
│   ├── engine/        # 仿真引擎内核 (LangGraph 调度)
│   ├── agents/        # 基础智能体模块
│   ├── llm/           # 大模型统一适配层
│   ├── memory/        # 记忆与存储层 (Chroma)
│   ├── parser/        # 结果解析与评估
│   └── registry.py    # 扩展注册表 - 闭源模块唯一入口
├── examples/          # 开源示例
├── ui/                # 可视化展示 - 100% 开源
└── docs/              # 文档
```

## 模块职责

| 模块 | 职责 |
|------|------|
| engine | 构建 LangGraph 状态图，定义节点流转，调度生命周期钩子 |
| agents | Agent 抽象基类 (perceive/think/act)，默认消费者/决策者实现 |
| llm | 统一 LLM 接口，支持 OpenAI、Gemini、通义千问 |
| memory | Chroma 向量存储，基础信息提取 |
| parser | 时序结果解析，供 UI 图表使用 |
| registry | 插件注册、钩子注册与触发，闭源模块入口 |

## 扩展机制

闭源商业模块通过 `Registry` 进行注册：

1. **插件注册**: `registry.register_plugin(name, plugin)`
2. **钩子注册**: `registry.register_hook(hook_name, callback)`
3. **钩子触发**: 由 engine 在关键节点调用 `registry.emit_hook(...)`

预定义钩子: `before_simulation`, `after_step`, `after_simulation`, `on_error`

## 技术栈

- **调度**: LangGraph
- **存储**: Chroma
- **UI**: Streamlit
- **配置**: PyYAML
- **校验**: Pydantic
