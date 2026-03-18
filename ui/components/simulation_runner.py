"""
仿真执行与进度展示模块

启动仿真、实时展示进度、异常处理。
"""

from __future__ import annotations

import sys
from pathlib import Path

# 项目根目录加入路径
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from presim_core.engine import SimulationEngine
from presim_core.parser import SimulationResultParser
from presim_core.parser import ParseResult

from ui.utils import build_config_from_params


def run_simulation(
    params: dict,
    progress_callback=None,
) -> tuple[object, ParseResult | None, str | None]:
    """
    执行仿真，返回最终状态、解析结果、错误信息

    Args:
        params: 来自 config_panel 的参数字典
        progress_callback: 每步完成时调用 (step, max_steps)，用于实时更新 UI

    Returns:
        (final_state, parse_result, error_message)
        error_message 非空时表示执行失败
    """
    try:
        config = build_config_from_params(params)
        max_steps = config.get("simulation", {}).get("steps", 6)

        engine = SimulationEngine(
            config=config,
            agent_types=["consumer", "decision"],
            max_steps=max_steps,
        )
        engine.build_graph()

        final_state = None
        for step, state in engine.stream():
            final_state = state
            if progress_callback:
                progress_callback(step, max_steps)

        if final_state is None:
            final_state, _ = engine.run()

        # 解析结果
        parser_config = config.get("parser", config)
        parser = SimulationResultParser(config=parser_config)
        parse_result = parser.parse(final_state)

        return final_state, parse_result, None

    except Exception as e:
        return None, None, str(e)


def render_progress_display(step: int, max_steps: int) -> None:
    """渲染进度展示（step 为已完成的月数，1-indexed）"""
    progress = step / max_steps if max_steps else 0
    st.progress(min(1.0, progress))
    st.caption(f"第 {step} / {max_steps} 月 完成")
