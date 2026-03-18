"""
风险预警看板 - 分等级列出风险点

标注风险等级、影响范围、发生时间。
"""

from __future__ import annotations

from typing import Optional

import streamlit as st

from presim_core.parser import ParseResult, RiskItem


def _risk_icon(level: str) -> str:
    if level == "high":
        return "🔴"
    if level == "medium":
        return "🟡"
    return "🟢"


def render_risk_panel(parse_result: Optional[ParseResult]) -> None:
    """
    渲染风险预警看板

    Args:
        parse_result: 解析结果，None 时不渲染
    """
    if parse_result is None:
        st.info("暂无数据，请先运行仿真")
        return

    risks = parse_result.risks
    if not risks:
        st.success("未识别到显著风险点，建议持续关注经营指标")
        return

    st.markdown("#### ⚠️ 核心风险点")

    for r in risks:
        icon = _risk_icon(r.level)
        level_cn = {"high": "高", "medium": "中", "low": "低"}.get(r.level, r.level)
        with st.container():
            st.markdown(f"**{icon} [{level_cn}风险]** {r.content}")
            if r.step is not None:
                st.caption(f"发生时间：第 {r.step + 1} 月")
            if r.impact:
                st.caption(f"影响：{r.impact}")
            if r.suggestion:
                st.caption(f"建议：{r.suggestion}")
            st.divider()
