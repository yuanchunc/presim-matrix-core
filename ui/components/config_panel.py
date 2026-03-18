"""
参数配置面板 - 左侧栏

用户可填写/修改开店核心参数，有默认值，支持一键启动或自定义调整。
"""

from __future__ import annotations

from typing import Any, Dict

import streamlit as st

from ui.utils import get_default_params


def render_config_panel() -> Dict[str, Any]:
    """
    渲染参数配置面板，返回当前参数字典

    Returns:
        参数字典，可直接用于 build_config_from_params
    """
    defaults = get_default_params()

    st.subheader("📋 参数配置")
    st.caption("使用默认值可直接启动，或按需调整")

    # 基础信息
    with st.expander("基础信息", expanded=True):
        initial_capital = st.number_input(
            "启动资金（元）",
            min_value=50000,
            max_value=500000,
            value=defaults["initial_capital"],
            step=10000,
            help="可用于开店的全部资金，含加盟费、装修、设备、首月运营",
        )
        business_mode = st.selectbox(
            "经营模式",
            options=["franchise", "self_owned"],
            format_func=lambda x: "加盟" if x == "franchise" else "自营",
            index=0,
            help="加盟需支付加盟费和品牌使用费，自营无此成本",
        )
        city = st.text_input("城市", value=defaults["city"], help="开店所在城市")
        area_type = st.selectbox(
            "商圈类型",
            options=["写字楼商圈", "大学城", "商业街", "社区"],
            index=0,
            help="不同商圈客流和竞争不同",
        )
        simulation_months = st.number_input(
            "仿真周期（月）",
            min_value=3,
            max_value=24,
            value=defaults["simulation_months"],
            help="预演多少个月的经营情况",
        )

    # 成本配置
    with st.expander("成本配置"):
        rent_monthly = st.number_input(
            "月租金（元）",
            min_value=3000,
            max_value=50000,
            value=defaults["rent_monthly"],
            step=1000,
            help="门店月租",
        )
        labor_monthly = st.number_input(
            "月人工（元）",
            min_value=6000,
            max_value=30000,
            value=defaults["labor_monthly"],
            step=1000,
            help="2-3人工资合计",
        )
        if business_mode == "franchise":
            franchise_fee = st.number_input(
                "加盟费（元）",
                min_value=0,
                max_value=200000,
                value=defaults["franchise_fee"],
                step=5000,
                help="一次性加盟费",
            )
            franchise_royalty = st.slider(
                "品牌使用费（%）",
                min_value=0.0,
                max_value=0.1,
                value=defaults["franchise_royalty"],
                step=0.01,
                format="%.0f%%",
                help="按月营收比例收取",
            )
        else:
            franchise_fee = 0
            franchise_royalty = 0.0
        equipment_deposit = st.number_input(
            "装修/设备投入（元）",
            min_value=0,
            max_value=100000,
            value=defaults["equipment_deposit"],
            step=5000,
            help="首月一次性支出",
        )
        material_ratio = st.slider(
            "原料成本占比",
            min_value=0.2,
            max_value=0.6,
            value=defaults["material_ratio"],
            step=0.01,
            format="%.0f%%",
            help="原料成本占营收比例",
        )
        utilities_monthly = st.number_input(
            "水电物业（元/月）",
            min_value=500,
            max_value=5000,
            value=defaults["utilities_monthly"],
            step=100,
        )
        marketing_monthly = st.number_input(
            "推广费用（元/月）",
            min_value=0,
            max_value=5000,
            value=defaults["marketing_monthly"],
            step=100,
        )

    # 定价
    with st.expander("定价策略"):
        base_price = st.number_input(
            "基础款单价（元/杯）",
            min_value=8,
            max_value=30,
            value=defaults["base_price"],
            help="最便宜款式的价格",
        )
        avg_cup_price = st.number_input(
            "平均客单价（元）",
            min_value=10,
            max_value=35,
            value=defaults["avg_cup_price"],
            help="考虑不同款式后的平均客单价",
        )

    # 市场配置
    with st.expander("市场配置"):
        competitors_nearby = st.number_input(
            "周边竞品数量",
            min_value=0,
            max_value=15,
            value=defaults["competitors_nearby"],
            help="同商圈内奶茶店数量，影响客流分流",
        )
        office_workers = st.number_input(
            "目标客群人数",
            min_value=500,
            max_value=10000,
            value=defaults["office_workers"],
            help="写字楼商圈为白领人数，大学城为学生人数",
        )
        foot_traffic = st.slider(
            "人流系数",
            min_value=0.3,
            max_value=1.0,
            value=defaults["foot_traffic"],
            step=0.05,
            help="0-1，反映选址人流量",
        )

    return {
        "initial_capital": initial_capital,
        "business_mode": business_mode,
        "city": city,
        "area_type": area_type,
        "simulation_months": simulation_months,
        "rent_monthly": rent_monthly,
        "labor_monthly": labor_monthly,
        "franchise_fee": franchise_fee,
        "franchise_royalty": franchise_royalty,
        "equipment_deposit": equipment_deposit,
        "material_ratio": material_ratio,
        "utilities_monthly": utilities_monthly,
        "marketing_monthly": marketing_monthly,
        "base_price": base_price,
        "avg_cup_price": avg_cup_price,
        "competitors_nearby": competitors_nearby,
        "office_workers": office_workers,
        "foot_traffic": foot_traffic,
    }


def render_export_config(params: Dict[str, Any]) -> None:
    """导出当前配置为 JSON 文件"""
    import json
    st.download_button(
        "📥 导出配置",
        data=json.dumps(params, ensure_ascii=False, indent=2),
        file_name="milk_tea_config.json",
        mime="application/json",
        use_container_width=True,
    )
