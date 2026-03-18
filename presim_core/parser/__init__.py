"""
结果解析与评估

解析仿真输出为结构化结论、可视化数据、风险提示，
支持配置化适配不同场景，预留闭源深度归因扩展。
"""

from presim_core.parser.result_parser import (
    BaseResultParser,
    SimulationResultParser,
    ResultParser,
    ParseResult,
    KeyEvent,
    RiskItem,
)

__all__ = [
    "BaseResultParser",
    "SimulationResultParser",
    "ResultParser",
    "ParseResult",
    "KeyEvent",
    "RiskItem",
]
