"""
关键演化节点 - 时间线展示

展示仿真过程中的关键事件、转折点、风险爆发点。
"""

from __future__ import annotations

from typing import Optional

import streamlit as st

from presim_core.parser import ParseResult


def render_timeline_panel(parse_result: Optional[ParseResult]) -> None:
    """
    渲染关键演化节点时间线

    Args:
        parse_result: 解析结果，None 时不渲染
    """
    if parse_result is None:
        st.info("暂无数据，请先运行仿真")
        return

    events = parse_result.key_events
    if not events:
        st.info("无关键事件记录")
        return

    st.markdown("#### 📅 演化关键节点")

    for e in events[:15]:
        month = e.step + 1
        with st.container():
            st.markdown(f"**第 {month} 月** · {e.description}")
            if e.impact:
                st.caption(f"影响：{e.impact}")
            st.divider()
