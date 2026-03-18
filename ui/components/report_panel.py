"""
完整仿真报告 - Markdown 格式

支持一键复制、导出 Markdown / JSON。
"""

from __future__ import annotations

import json
from typing import Optional

import streamlit as st

from presim_core.parser import ParseResult

from ui.utils import build_full_report


def render_report_panel(
    parse_result: Optional[ParseResult],
    config: dict,
) -> None:
    """
    渲染完整报告面板

    Args:
        parse_result: 解析结果，None 时不渲染
        config: 仿真配置
    """
    if parse_result is None:
        st.info("暂无数据，请先运行仿真")
        return

    report = build_full_report(parse_result, config)

    st.markdown("#### 📄 完整仿真报告")

    st.code(report, language="markdown")

    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            label="📥 导出 Markdown",
            data=report,
            file_name="milk_tea_simulation_report.md",
            mime="text/markdown",
            use_container_width=True,
        )
    with col2:
        json_data = json.dumps({
            "config": config,
            "summary": parse_result.summary,
            "statistics": parse_result.statistics,
            "risks": [{"level": r.level, "content": r.content} for r in parse_result.risks],
            "timeline_data": parse_result.timeline_data,
        }, ensure_ascii=False, indent=2)
        st.download_button(
            label="📥 导出 JSON 数据",
            data=json_data,
            file_name="milk_tea_simulation_result.json",
            mime="application/json",
            use_container_width=True,
        )
