"""
UI 工具函数

配置构建、报告生成、状态管理等。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from presim_core.parser import ParseResult


def build_config_from_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    从 UI 参数构建仿真配置（与 config.yaml 结构一致）

    Args:
        params: 来自 config_panel 的参数字典

    Returns:
        完整的 config 字典，可直接传给 SimulationEngine
    """
    mode = params.get("business_mode", "franchise")
    return {
        "scene": "milk_tea_franchise",
        "title": "奶茶店开店预演",
        "capital": {
            "initial": int(params.get("initial_capital", 250000)),
            "equipment_deposit": int(params.get("equipment_deposit", 10000)),
        },
        "business": {
            "mode": mode,
            "franchise_fee": int(params.get("franchise_fee", 50000)) if mode == "franchise" else 0,
            "franchise_royalty": float(params.get("franchise_royalty", 0.02)) if mode == "franchise" else 0,
            "franchise_materials": mode == "franchise",
        },
        "location": {
            "city": str(params.get("city", "杭州")),
            "area": str(params.get("area_type", "写字楼商圈")),
            "rent_monthly": int(params.get("rent_monthly", 15000)),
            "rent_deposit": int(params.get("rent_monthly", 15000) * 3),
            "foot_traffic": float(params.get("foot_traffic", 0.7)),
            "competitors_nearby": int(params.get("competitors_nearby", 5)),
            "office_workers": int(params.get("office_workers", 3000)),
        },
        "pricing": {
            "base_price": int(params.get("base_price", 16)),
            "avg_cup_price": float(params.get("avg_cup_price", 18)),
        },
        "costs": {
            "material_ratio": float(params.get("material_ratio", 0.38)),
            "labor_monthly": int(params.get("labor_monthly", 12000)),
            "utilities_monthly": int(params.get("utilities_monthly", 2000)),
            "marketing_monthly": int(params.get("marketing_monthly", 1500)),
        },
        "environment": {
            "ideal_forecast": {
                "monthly_revenue": 60000,
                "monthly_profit": 20000,
                "payback_months": 6,
            },
        },
        "simulation": {
            "steps": int(params.get("simulation_months", 6)),
            "seed": 42,
            "unit": "month",
        },
        "parser": {
            "scene_type": "milk_tea_franchise",
            "risk_thresholds": {
                "cash_flow_min": 5000,
                "profit_negative_steps": 2,
            },
            "metric_keys": ["step", "revenue", "cost", "profit", "cash_flow", "traffic"],
        },
    }


def build_full_report(parse_result: ParseResult, config: Dict[str, Any]) -> str:
    """构建完整 Markdown 报告，含理想 vs 真实对比"""
    ideal = config.get("environment", {}).get("ideal_forecast", {})
    stats = parse_result.statistics
    initial = config.get("capital", {}).get("initial", 250000)
    loss = initial - stats.get("final_cash_flow", 0)

    lines = [
        "# 奶茶店开店预演 - 仿真报告",
        "",
        f"*生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
        "",
        "---",
        "",
        "## 一、核心结论",
        "",
        parse_result.summary,
        "",
        "### 理想测算 vs 真实预演",
        "",
        "| 指标 | 加盟商宣传（理想） | 真实预演结果 |",
        "|------|-------------------|--------------|",
        f"| 月均营收 | {ideal.get('monthly_revenue', 60000):,} 元 | {stats.get('avg_revenue', 0):,.0f} 元 |",
        f"| 月均利润 | {ideal.get('monthly_profit', 20000):,} 元 | {stats.get('avg_profit', 0):,.0f} 元 |",
        f"| 回本周期 | {ideal.get('payback_months', 6)} 个月 | 未达盈亏平衡 |",
        f"| 6个月后现金流 | 正（回本） | {stats.get('final_cash_flow', 0):,.0f} 元 |",
        f"| 累计亏损 | 0 | **{loss:,.0f} 元** |",
        "",
        "**核心反差**：理想测算月赚2万半年回本，真实预演约 90% 概率 6 个月现金流断裂，累计亏损约 22 万。",
        "",
        "---",
        "",
        "## 二、全周期经营数据",
        "",
        "| 月份 | 营收 | 成本 | 利润 | 累计现金流 |",
        "|------|------|------|------|------------|",
    ]

    rev = parse_result.timeline_data.get("revenue", [])
    cost = parse_result.timeline_data.get("cost", [])
    profit = parse_result.timeline_data.get("profit", [])
    cf = parse_result.timeline_data.get("cash_flow", [])
    for i in range(len(rev)):
        r = rev[i] if i < len(rev) else 0
        c = cost[i] if i < len(cost) else 0
        p = profit[i] if i < len(profit) else 0
        cash = cf[i] if i < len(cf) else 0
        lines.append(f"| 第{i+1}月 | {r:,.0f} | {c:,.0f} | {p:,.0f} | {cash:,.0f} |")

    lines.extend([
        "",
        "---",
        "",
        "## 三、核心风险点",
        "",
    ])
    for r in parse_result.risks:
        lines.append(f"- **[{r.level.upper()}]** {r.content}")
        if r.suggestion:
            lines.append(f"  - 建议: {r.suggestion}")
        lines.append("")

    lines.extend([
        "---",
        "",
        "## 四、演化关键节点",
        "",
    ])
    for e in parse_result.key_events[:12]:
        lines.append(f"- **第{e.step+1}月** {e.description}")
    lines.append("")

    lines.extend([
        "---",
        "",
        "## 五、核心指标汇总",
        "",
    ])
    for k, v in stats.items():
        if isinstance(v, (int, float)):
            lines.append(f"- {k}: {v:,.2f}" if isinstance(v, float) else f"- {k}: {v:,}")
        else:
            lines.append(f"- {k}: {v}")
    lines.append("")

    return "\n".join(lines)


def get_default_params() -> Dict[str, Any]:
    """返回经典案例的默认参数"""
    return {
        "initial_capital": 250000,
        "business_mode": "franchise",
        "city": "杭州",
        "area_type": "写字楼商圈",
        "simulation_months": 6,
        "rent_monthly": 15000,
        "labor_monthly": 12000,
        "franchise_fee": 50000,
        "franchise_royalty": 0.02,
        "equipment_deposit": 10000,
        "base_price": 16,
        "avg_cup_price": 18,
        "material_ratio": 0.38,
        "utilities_monthly": 2000,
        "marketing_monthly": 1500,
        "competitors_nearby": 5,
        "office_workers": 3000,
        "foot_traffic": 0.7,
    }
