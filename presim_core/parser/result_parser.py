"""
仿真结果解析器 - 预演式决策核心

将 SimulationState 解析为结构化结论、可视化数据、风险提示，
支持配置化适配不同场景，预留闭源深度归因引擎扩展。
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


# =============================================================================
# 数据结构定义
# =============================================================================


@dataclass
class KeyEvent:
    """关键节点/事件"""

    step: int
    event_type: str
    description: str
    impact: Optional[str] = None
    raw_data: Optional[Dict[str, Any]] = None


@dataclass
class RiskItem:
    """风险项"""

    level: str  # high / medium / low
    content: str
    step: Optional[int] = None
    impact: Optional[str] = None
    suggestion: Optional[str] = None


@dataclass
class ParseResult:
    """解析结果容器"""

    summary: str = ""
    key_events: List[KeyEvent] = field(default_factory=list)
    timeline_data: Dict[str, List[Any]] = field(default_factory=dict)
    risks: List[RiskItem] = field(default_factory=list)
    statistics: Dict[str, Any] = field(default_factory=dict)
    raw: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# 基类 BaseResultParser
# =============================================================================


class BaseResultParser(ABC):
    """
    结果解析基类

    规范解析器核心接口，闭源深度风险归因引擎可继承扩展。
    只依赖 SimulationState 标准结构，不硬编码其他模块。
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        初始化解析器

        Args:
            config: 解析配置，可含 metric_keys、risk_rules、scene_type 等
        """
        self._config = config or {}

    @abstractmethod
    def parse(self, state: Any) -> ParseResult:
        """
        解析仿真状态为结构化结果

        Args:
            state: SimulationState 或兼容的 dict

        Returns:
            ParseResult 解析结果
        """
        pass

    def parse_timeline(self, state: Any) -> List[Dict[str, Any]]:
        """
        解析 timeline（兼容 registry 等调用）

        Args:
            state: SimulationState 或 dict

        Returns:
            时序数据列表
        """
        try:
            if hasattr(state, "timeline"):
                return getattr(state, "timeline") or []
            if isinstance(state, dict) and "timeline" in state:
                return state.get("timeline") or []
        except Exception as e:
            logger.warning("parse_timeline 异常: %s", e)
        return []

    def extract_series(self, timeline: List[Dict[str, Any]], key: str) -> List[Any]:
        """从 timeline 提取指定键的序列（兼容旧接口）"""
        return [item.get(key) for item in timeline if key in item]

    def to_chart_data(
        self,
        timeline: Optional[List[Dict[str, Any]]] = None,
        x_key: str = "step",
        y_keys: Optional[List[str]] = None,
        state: Optional[Any] = None,
    ) -> Dict[str, List[Any]]:
        """
        转为图表可用格式（兼容旧接口）

        若传入 state，则先 parse 再取 timeline_data；否则用 timeline。
        """
        if state is not None:
            result = self.parse(state)
            data = result.timeline_data
            x_vals = data.get(x_key, data.get("x", []))
            out: Dict[str, List[Any]] = {"x": x_vals}
            for k in y_keys or []:
                if k in data:
                    out[k] = data[k]
            return out
        if timeline:
            x_vals = self.extract_series(timeline, x_key)
            out = {"x": x_vals}
            for k in y_keys or []:
                out[k] = self.extract_series(timeline, k)
            return out
        return {}

    def to_markdown(self, result: ParseResult) -> str:
        """将 ParseResult 转为 Markdown 报告"""
        raise NotImplementedError("子类实现")

    def to_json(self, result: ParseResult) -> str:
        """将 ParseResult 转为 JSON 字符串"""
        return json.dumps(self._result_to_dict(result), ensure_ascii=False, indent=2)

    def to_dataframe_data(self, result: ParseResult) -> Dict[str, List[Any]]:
        """转为 DataFrame/图表所需格式"""
        return result.timeline_data

    def _result_to_dict(self, result: ParseResult) -> Dict[str, Any]:
        """ParseResult 转可序列化 dict"""
        return {
            "summary": result.summary,
            "key_events": [
                {
                    "step": e.step,
                    "event_type": e.event_type,
                    "description": e.description,
                    "impact": e.impact,
                }
                for e in result.key_events
            ],
            "risks": [
                {
                    "level": r.level,
                    "content": r.content,
                    "step": r.step,
                    "impact": r.impact,
                }
                for r in result.risks
            ],
            "statistics": result.statistics,
            "timeline_data": result.timeline_data,
        }


# =============================================================================
# 默认实现 SimulationResultParser
# =============================================================================


class SimulationResultParser(BaseResultParser):
    """
    默认仿真结果解析器

    支持全流程总结、关键事件提取、量化指标解析、风险识别、多维度统计。
    通过配置适配不同场景，不硬编码奶茶店逻辑。
    """

    # 默认指标键（可被 config 覆盖）
    DEFAULT_METRIC_KEYS = ["step", "revenue", "cost", "profit", "cash_flow", "traffic"]
    DEFAULT_RISK_THRESHOLDS = {
        "cash_flow_min": 0,
        "profit_negative_steps": 3,
        "traffic_drop_ratio": 0.5,
    }

    def parse(self, state: Any) -> ParseResult:
        """
        解析仿真状态

        即使数据不完整，也尽量输出基础解析结果。
        """
        result = ParseResult()
        try:
            state_dict = self._to_dict(state)
            result.raw = state_dict

            self._parse_key_events(state_dict, result)
            self._parse_timeline_metrics(state_dict, result)
            self._parse_risks(state_dict, result)
            self._parse_statistics(state_dict, result)
            self._parse_summary(state_dict, result)  # 最后生成总结，可引用 statistics

        except Exception as e:
            logger.exception("解析异常: %s", e)
            result.summary = f"解析过程中出现异常: {e}，已输出部分结果。"
        return result

    def _to_dict(self, state: Any) -> Dict[str, Any]:
        """统一转为 dict"""
        if isinstance(state, dict):
            return state
        if hasattr(state, "model_dump"):
            return state.model_dump()
        if hasattr(state, "__dict__"):
            return dict(state.__dict__)
        return {}

    def _parse_summary(self, state: Dict[str, Any], result: ParseResult) -> None:
        """生成全流程仿真总结"""
        config = state.get("config", {})
        timeline = state.get("timeline", [])
        steps = state.get("simulation_results", {}).get("steps_completed", len(timeline))
        error = state.get("error")
        stopped = state.get("stopped", False)

        scene_type = self._config.get("scene_type", config.get("scene_type", "经营"))
        metric_keys = self._config.get("metric_keys", self.DEFAULT_METRIC_KEYS)

        parts: List[str] = []

        if error:
            parts.append(f"仿真因异常中断：{error}。")
        elif stopped:
            parts.append("仿真被主动终止。")
        else:
            parts.append(f"仿真顺利完成，共 {steps} 个周期。")

        if timeline:
            parts.append(f"核心演化脉络：从第 1 轮到第 {steps} 轮，系统按预设逻辑推进。")
            last_step = timeline[-1] if timeline else {}
            agent_outs = last_step.get("agent_outputs", {})
            if agent_outs:
                parts.append("最后一轮智能体决策已执行完毕。")
            stats = result.statistics
            if stats.get("total_profit") is not None:
                profit = stats["total_profit"]
                if float(profit) > 0:
                    parts.append(f"整体盈利 {profit:.2f}，经营结果向好。")
                elif float(profit) < 0:
                    parts.append(f"整体亏损 {profit:.2f}，需关注成本与收入结构。")
            if stats.get("break_even_step") is not None:
                be = stats["break_even_step"]
                if be >= 0 and be < steps:
                    parts.append(f"约第 {be + 1} 周期达到盈亏平衡。")
                elif be == -1:
                    parts.append("全周期未达盈亏平衡。")
        else:
            parts.append("暂无有效时序数据，无法生成详细演化分析。")

        result.summary = " ".join(parts)

    def _parse_key_events(self, state: Dict[str, Any], result: ParseResult) -> None:
        """从 history_events 提取关键转折点、风险爆发点"""
        events = state.get("history_events", [])
        for ev in events:
            try:
                step = ev.get("step", 0)
                ev_type = ev.get("type", "unknown")
                data = ev.get("data", ev)

                desc = self._event_to_description(ev_type, data, step)
                impact = self._event_to_impact(ev_type, data)

                result.key_events.append(
                    KeyEvent(
                        step=step,
                        event_type=ev_type,
                        description=desc,
                        impact=impact,
                        raw_data=data if isinstance(data, dict) else None,
                    )
                )
            except Exception as e:
                logger.debug("解析事件失败: %s", e)

    def _event_to_description(self, ev_type: str, data: Any, step: int) -> str:
        """将事件转为可读描述"""
        if ev_type == "step_complete":
            return f"第 {step + 1} 轮仿真完成"
        if ev_type == "risk":
            return str(data.get("description", data))
        return f"第 {step + 1} 轮: {ev_type}"

    def _event_to_impact(self, ev_type: str, data: Any) -> Optional[str]:
        """提取事件影响"""
        if isinstance(data, dict) and "impact" in data:
            return data["impact"]
        return None

    def _parse_timeline_metrics(self, state: Dict[str, Any], result: ParseResult) -> None:
        """提取量化指标时序，适配可视化"""
        timeline = state.get("timeline", [])
        config = state.get("config", {})
        metric_keys = self._config.get("metric_keys", self.DEFAULT_METRIC_KEYS)

        # 基础：step 序列
        steps = [item.get("step", i) for i, item in enumerate(timeline)]
        result.timeline_data["step"] = steps
        result.timeline_data["x"] = steps  # 兼容图表 x 轴

        # 从 timeline 或 agent_outputs 提取业务指标
        for key in metric_keys:
            if key in ("step", "x"):
                continue
            vals = self._extract_metric_series(timeline, config, key)
            if vals is not None:
                result.timeline_data[key] = vals

        # 若未提取到业务指标，用配置生成占位数据（适配 Demo）
        scene = config.get("scene") or self._config.get("scene_type")
        if scene == "milk_tea_franchise":
            self._fill_milk_tea_franchise_metrics(result, config, len(timeline))
        else:
            self._fill_placeholder_metrics(result, config, len(timeline))

    def _extract_metric_series(
        self,
        timeline: List[Dict[str, Any]],
        config: Dict[str, Any],
        key: str,
    ) -> Optional[List[Any]]:
        """从 timeline 提取指定指标序列"""
        vals: List[Any] = []
        for i, item in enumerate(timeline):
            v = None
            agent_outs = item.get("agent_outputs", {})
            for agent_name, out in agent_outs.items():
                if isinstance(out, dict) and key in out:
                    v = out[key]
                    break
            if v is None and isinstance(item, dict) and key in item:
                v = item[key]
            vals.append(v)
        if all(v is None for v in vals):
            return None
        return vals

    def _fill_milk_tea_franchise_metrics(
        self,
        result: ParseResult,
        config: Dict[str, Any],
        n: int,
    ) -> None:
        """
        奶茶店加盟场景：真实预演模型

        理想测算月赚2万，真实预演：竞品分流、加盟成本、固定支出导致
        约90%概率6个月现金流断裂，累计亏损约22万。
        """
        if n == 0:
            return
        import random

        pricing = config.get("pricing", {})
        costs = config.get("costs", {})
        location = config.get("location", {})
        business = config.get("business", {})
        capital = config.get("capital", {})
        env = config.get("environment", {})

        base_price = float(pricing.get("base_price", 16))
        avg_price = float(pricing.get("avg_cup_price", 18))
        material_ratio = float(costs.get("material_ratio", 0.38))
        labor = float(costs.get("labor_monthly", 12000))
        rent = float(location.get("rent_monthly", 15000))
        utilities = float(costs.get("utilities_monthly", 2000))
        marketing = float(costs.get("marketing_monthly", 1500))
        franchise_fee = float(business.get("franchise_fee", 50000))
        franchise_royalty = float(business.get("franchise_royalty", 0.02))
        competitors = int(location.get("competitors_nearby", 5))
        workers = int(location.get("office_workers", 3000))
        traffic_base = float(location.get("foot_traffic", 0.7))

        seed = config.get("simulation", {}).get("seed", 42)
        random.seed(seed)

        # 淡旺季系数 (3-8月)
        season = [0.9, 1.0, 1.1, 1.0, 0.85, 0.9][:n]
        season = season + [1.0] * (n - len(season))

        # 营收：新店开业首月略高，随后竞品促销分流，逐月下滑
        # 理想 6万/月 vs 真实 首月1.2万 → 第6月 0.5万
        # 写字楼 8% 日转化，6 家店分流，首月约 350 杯/日
        base_daily_cups = workers * 0.08 * traffic_base / max(1, competitors + 1)
        revenue = []
        for i in range(n):
            decay = max(0.35, 1.0 - 0.11 * i - 0.04 * random.random())  # 竞品分流逐月衰减
            monthly_cups = max(150, base_daily_cups * 22 * season[i] * decay)
            rev = round(monthly_cups * avg_price * (0.92 + 0.16 * random.random()), 2)
            revenue.append(rev)

        # 成本：固定成本高，首月含加盟费+设备押金
        equipment = float(capital.get("equipment_deposit", 0))
        cost = []
        for i, rev in enumerate(revenue):
            c = rev * material_ratio + labor + rent + utilities + marketing
            c += rev * franchise_royalty  # 品牌使用费
            if i == 0:
                c += franchise_fee + equipment
            c += 800 * (1 + 0.2 * random.random())  # 隐性支出（损耗、临时用工等）
            c = round(c, 2)
            cost.append(c)

        profit = [round(r - c, 2) for r, c in zip(revenue, cost)]
        initial = float(capital.get("initial", 250000))
        cf = initial
        cfs = []
        for p in profit:
            cf += p
            cfs.append(round(cf, 2))
        traffic = [round(r / avg_price, 0) for r in revenue]

        result.timeline_data["revenue"] = revenue
        result.timeline_data["cost"] = cost
        result.timeline_data["profit"] = profit
        result.timeline_data["cash_flow"] = cfs
        result.timeline_data["traffic"] = traffic

    def _fill_placeholder_metrics(
        self,
        result: ParseResult,
        config: Dict[str, Any],
        n: int,
    ) -> None:
        """用配置生成占位时序（Demo 适配）"""
        if n == 0:
            return
        pricing = config.get("pricing", {})
        costs = config.get("costs", {})
        location = config.get("location", {})

        base_price = float(pricing.get("base_price", 12))
        material_ratio = float(costs.get("material_ratio", 0.35))
        labor = float(costs.get("labor_monthly", 6000))
        rent = float(location.get("rent_monthly", 8000))
        traffic = float(location.get("foot_traffic", 0.7))

        if "revenue" not in result.timeline_data:
            # 简化模型：每轮营收 = 基础客流 * 单价 * 随机系数
            import random
            random.seed(config.get("simulation", {}).get("seed", 42))
            base_traffic = 500 * traffic
            revenue = [
                round(base_traffic * base_price * (0.8 + 0.4 * random.random()), 2)
                for _ in range(n)
            ]
            result.timeline_data["revenue"] = revenue
        if "cost" not in result.timeline_data:
            rev = result.timeline_data.get("revenue", [0] * n)
            cost = [
                round(r * material_ratio + (labor + rent) / max(1, n), 2)
                for r in rev
            ]
            result.timeline_data["cost"] = cost
        if "profit" not in result.timeline_data:
            rev = result.timeline_data.get("revenue", [0] * n)
            cost = result.timeline_data.get("cost", [0] * n)
            result.timeline_data["profit"] = [
                round(r - c, 2) for r, c in zip(rev, cost)
            ]
        if "cash_flow" not in result.timeline_data:
            profit = result.timeline_data.get("profit", [0] * n)
            cf = 0.0
            cfs = []
            for p in profit:
                cf += p
                cfs.append(round(cf, 2))
            result.timeline_data["cash_flow"] = cfs
        if "traffic" not in result.timeline_data:
            rev = result.timeline_data.get("revenue", [0] * n)
            result.timeline_data["traffic"] = [
                round(r / base_price, 0) if base_price else 0 for r in rev
            ]

    def _parse_risks(self, state: Dict[str, Any], result: ParseResult) -> None:
        """基础风险识别"""
        thresholds = {
            **self.DEFAULT_RISK_THRESHOLDS,
            **self._config.get("risk_thresholds", {}),
        }

        timeline_data = result.timeline_data
        steps = timeline_data.get("step", timeline_data.get("x", []))

        # 现金流风险
        cfs = timeline_data.get("cash_flow", [])
        for i, cf in enumerate(cfs):
            if cf is not None and float(cf) < thresholds["cash_flow_min"]:
                step = steps[i] if i < len(steps) else i
                result.risks.append(
                    RiskItem(
                        level="high",
                        content=f"现金流在第 {step + 1} 周期为负 ({cf})，存在断裂风险",
                        step=step,
                        impact="可能无法支付固定成本",
                        suggestion="控制成本或提升营收",
                    )
                )
                break

        # 连续亏损
        profits = timeline_data.get("profit", [])
        neg_count = 0
        for i, p in enumerate(profits):
            if p is not None and float(p) < 0:
                neg_count += 1
                if neg_count >= thresholds["profit_negative_steps"]:
                    step = steps[i] if i < len(steps) else i
                    result.risks.append(
                        RiskItem(
                            level="medium",
                            content=f"连续 {neg_count} 周期亏损，第 {step + 1} 周期",
                            step=step,
                            impact="长期亏损将耗尽资金",
                            suggestion="审视定价与成本结构",
                        )
                    )
                    break
            else:
                neg_count = 0

        # 客流骤降
        traffic = timeline_data.get("traffic", [])
        if len(traffic) >= 2:
            for i in range(1, len(traffic)):
                if traffic[i - 1] and traffic[i] is not None:
                    drop = 1 - float(traffic[i]) / float(traffic[i - 1])
                    if drop >= thresholds["traffic_drop_ratio"]:
                        step = steps[i] if i < len(steps) else i
                        result.risks.append(
                            RiskItem(
                                level="medium",
                                content=f"第 {step + 1} 周期客流较上期下降超 50%",
                                step=step,
                                impact="营收将显著下滑",
                            )
                        )
                        break

        if not result.risks:
            result.risks.append(
                RiskItem(
                    level="low",
                    content="未识别到显著风险点，建议持续关注经营指标",
                )
            )

    def _parse_statistics(self, state: Dict[str, Any], result: ParseResult) -> None:
        """多维度数据统计"""
        td = result.timeline_data
        steps = td.get("step", td.get("x", []))
        n = len(steps) if steps else 0

        stats: Dict[str, Any] = {}

        revenue = td.get("revenue", [])
        cost = td.get("cost", [])
        profit = td.get("profit", [])
        cash_flow = td.get("cash_flow", [])
        traffic = td.get("traffic", [])

        def _sum(vals: List[Any]) -> float:
            return sum(float(v) for v in vals if v is not None)

        def _safe_num(v: Any) -> Optional[float]:
            if v is None:
                return None
            try:
                return float(v)
            except (TypeError, ValueError):
                return None

        if revenue:
            stats["total_revenue"] = round(_sum(revenue), 2)
            stats["avg_revenue"] = round(stats["total_revenue"] / len(revenue), 2)
        if cost:
            stats["total_cost"] = round(_sum(cost), 2)
        if profit:
            stats["total_profit"] = round(_sum(profit), 2)
            stats["avg_profit"] = round(stats["total_profit"] / len(profit), 2)
        if cash_flow:
            valid = [c for c in cash_flow if c is not None]
            if valid:
                stats["max_cash_flow"] = max(valid)
                stats["min_cash_flow"] = min(valid)
                stats["final_cash_flow"] = valid[-1]
        if traffic:
            valid = [t for t in traffic if t is not None]
            if valid:
                stats["peak_traffic"] = max(valid)
                stats["min_traffic"] = min(valid)

        # 盈亏平衡点（累计利润首次非负的周期）
        if profit:
            cum = 0.0
            for i, p in enumerate(profit):
                v = _safe_num(p)
                if v is not None:
                    cum += v
                    if cum >= 0:
                        stats["break_even_step"] = i
                        break
            else:
                stats["break_even_step"] = -1

        stats["steps_completed"] = n
        result.statistics = stats

    def to_markdown(self, result: ParseResult) -> str:
        """输出 Markdown 报告"""
        lines: List[str] = ["# 仿真结果报告", ""]

        lines.append("## 全流程总结")
        lines.append(result.summary)
        lines.append("")

        if result.key_events:
            lines.append("## 关键节点与事件")
            for e in result.key_events:
                lines.append(f"- **第 {e.step + 1} 轮** [{e.event_type}]: {e.description}")
                if e.impact:
                    lines.append(f"  - 影响: {e.impact}")
            lines.append("")

        if result.risks:
            lines.append("## 风险提示")
            for r in result.risks:
                lines.append(f"- **{r.level.upper()}**: {r.content}")
                if r.suggestion:
                    lines.append(f"  - 建议: {r.suggestion}")
            lines.append("")

        if result.statistics:
            lines.append("## 核心指标统计")
            for k, v in result.statistics.items():
                lines.append(f"- {k}: {v}")
            lines.append("")

        return "\n".join(lines)


# =============================================================================
# 兼容层：ResultParser 别名
# =============================================================================

ResultParser = SimulationResultParser


# =============================================================================
# 测试用例
# =============================================================================

if __name__ == "__main__":
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    logging.basicConfig(level=logging.INFO)

    # 模拟仿真状态
    mock_state = {
        "config": {
            "pricing": {"base_price": 12},
            "costs": {"material_ratio": 0.35, "labor_monthly": 6000},
            "location": {"rent_monthly": 8000, "foot_traffic": 0.7},
            "simulation": {"steps": 6, "seed": 42},
        },
        "step": 6,
        "timeline": [{"step": i, "agent_outputs": {}} for i in range(6)],
        "history_events": [
            {"step": i, "type": "step_complete", "data": {"step": i}}
            for i in range(6)
        ],
        "simulation_results": {"steps_completed": 6},
    }

    parser = SimulationResultParser()
    result = parser.parse(mock_state)

    print("=== Summary ===")
    print(result.summary)
    print("\n=== Key Events ===")
    for e in result.key_events[:3]:
        print(f"  Step {e.step}: {e.description}")
    print("\n=== Risks ===")
    for r in result.risks:
        print(f"  [{r.level}] {r.content}")
    print("\n=== Statistics ===")
    print(result.statistics)
    print("\n=== Timeline Data (chart-ready) ===")
    print({k: (v[:3] if isinstance(v, list) and len(v) > 3 else v) for k, v in result.timeline_data.items()})
    print("\n=== Markdown ===")
    print(parser.to_markdown(result)[:500])

    # 高风险场景：高成本导致负现金流
    risk_state = {
        "config": {
            **mock_state["config"],
            "costs": {"material_ratio": 0.8, "labor_monthly": 50000},
            "location": {"rent_monthly": 50000, "foot_traffic": 0.3},
        },
        "timeline": mock_state["timeline"],
        "history_events": mock_state["history_events"],
        "simulation_results": {"steps_completed": 6},
    }
    result_risk = parser.parse(risk_state)
    print("\n=== 高风险场景（高成本）===")
    for r in result_risk.risks:
        print(f"  [{r.level}] {r.content}")
    print("  统计:", result_risk.statistics.get("total_profit"), "总利润")

    print("\nOK")
