"""
时序数据图表 - 现金流、营收、利润、成本、客流

折线图 + 柱状图，直观展示经营数据变化。
"""

from __future__ import annotations

from typing import Optional

import pandas as pd
import streamlit as st

from presim_core.parser import ParseResult


def render_result_charts(parse_result: Optional[ParseResult]) -> None:
    """
    渲染时序图表

    Args:
        parse_result: 解析结果，None 时不渲染
    """
    if parse_result is None:
        st.info("暂无数据，请先运行仿真")
        return

    td = parse_result.timeline_data
    steps = td.get("step", td.get("x", []))
    n = len(steps)
    if n == 0:
        st.warning("无时序数据")
        return

    # 月份标签
    months = [f"第{i+1}月" for i in range(n)]
    df = pd.DataFrame({
        "月份": months,
        "营收": td.get("revenue", [0] * n),
        "成本": td.get("cost", [0] * n),
        "利润": td.get("profit", [0] * n),
        "累计现金流": td.get("cash_flow", [0] * n),
        "客流": td.get("traffic", [0] * n),
    })

    # 现金流折线图
    st.markdown("#### 📈 累计现金流变化")
    st.line_chart(df.set_index("月份")[["累计现金流"]], height=280)

    # 营收 vs 成本 vs 利润
    st.markdown("#### 📊 每月营收 / 成本 / 利润")
    st.bar_chart(df.set_index("月份")[["营收", "成本", "利润"]], height=280)

    # 客流变化
    st.markdown("#### 👥 每月客流（杯数）")
    st.line_chart(df.set_index("月份")[["客流"]], height=220)
