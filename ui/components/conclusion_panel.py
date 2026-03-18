"""
核心结论看板 - 仿真完成后第一时间呈现

用醒目方式呈现理想 vs 现实反差，突出核心结论。
"""

from __future__ import annotations

from typing import Optional

import streamlit as st

from presim_core.parser import ParseResult


def render_conclusion_panel(parse_result: Optional[ParseResult], config: dict) -> None:
    """
    渲染核心结论看板

    Args:
        parse_result: 解析结果，None 时显示占位
        config: 仿真配置
    """
    if parse_result is None:
        st.info("👆 点击「一键启动仿真」查看预演结果")
        return

    stats = parse_result.statistics
    ideal = config.get("environment", {}).get("ideal_forecast", {})
    initial = config.get("capital", {}).get("initial", 250000)
    final_cf = stats.get("final_cash_flow", 0)
    total_profit = stats.get("total_profit", 0)
    loss = initial - final_cf if final_cf is not None else abs(total_profit) if total_profit else 0

    # 核心结论 - 醒目展示
    st.markdown("### 🎯 核心结论")

    # 判断风险等级：现金流断裂 或 累计亏损超 15 万
    is_critical = final_cf is not None and (final_cf < 0 or loss > 150000)
    risk_prob = "约 90%" if loss > 150000 else "较低"

    if final_cf is not None and final_cf < 0:
        st.error(
            f"**{risk_prob} 概率 6 个月现金流断裂闭店**  \n"
            f"累计亏损约 **{loss:,.0f} 元**"
        )
    elif loss > 150000:
        cf_text = f"{final_cf:,.0f}" if final_cf is not None else "—"
        st.error(
            f"**累计亏损约 {loss:,.0f} 元**  \n"
            f"现金流剩余 **{cf_text} 元**，经营压力巨大"
        )
    else:
        cf_text = f"{final_cf:,.0f}" if final_cf is not None else "—"
        st.warning(f"现金流剩余 **{cf_text} 元**，需持续关注经营状况")

    # 理想 vs 真实 对比表
    st.markdown("#### 理想测算 vs 真实预演")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("月均营收", f"{stats.get('avg_revenue', 0):,.0f} 元", f"理想 {ideal.get('monthly_revenue', 60000):,}")
    with col2:
        st.metric("月均利润", f"{stats.get('avg_profit', 0):,.0f} 元", f"理想 {ideal.get('monthly_profit', 20000):,}")
    with col3:
        be = stats.get("break_even_step", -1)
        be_text = f"第{be+1}月" if be >= 0 else "未达"
        st.metric("盈亏平衡", be_text, "理想 6 个月")

    # 核心反差文案
    st.markdown("---")
    st.markdown(
        "**核心反差**：加盟商宣传「月赚 2 万、半年回本」，"
        "真实预演中竞品分流、固定成本高、客流衰减，导致现金流断裂。"
    )
