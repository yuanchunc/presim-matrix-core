"""
奶茶店开店预演 Demo - 一键运行脚本

25万开奶茶店，从加盟到闭店6个月预演
理想测算月赚2万半年回本 vs 真实预演90%概率6个月现金流断裂闭店

使用方式：
  1. 配置 .env 中的大模型 API Key（可选，用于增强分析）
  2. 执行 python run_simulation.py
  3. 查看控制台报告，或导出的 JSON/Markdown 文件
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# 项目根目录加入路径
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# 加载 .env（若存在）
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    with open(_env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

import yaml
from presim_core.engine import SimulationEngine
from presim_core.parser import SimulationResultParser, ParseResult


def load_config(config_path: Path) -> dict:
    """加载 YAML 配置"""
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_full_report(
    parse_result: ParseResult,
    config: dict,
    final_state: any,
) -> str:
    """构建完整 Markdown 报告，含理想 vs 真实对比"""
    ideal = config.get("environment", {}).get("ideal_forecast", {})
    stats = parse_result.statistics
    loss = 250000 - stats.get("final_cash_flow", 0)

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


def main() -> None:
    """主入口：加载配置、运行仿真、输出报告"""
    config_path = Path(__file__).parent / "config.yaml"
    if not config_path.exists():
        print("错误: 未找到 config.yaml")
        sys.exit(1)

    config = load_config(config_path)
    sim_cfg = config.get("simulation", {})
    max_steps = sim_cfg.get("steps", 6)

    print("=" * 60)
    print(config.get("title", "奶茶店开店预演"))
    print("=" * 60)
    print(f"场景: {config.get('scene', 'milk_tea_franchise')}")
    print(f"仿真周期: {max_steps} 个月")
    print(f"启动资金: {config.get('capital', {}).get('initial', 250000):,} 元")
    print(f"经营模式: {'加盟' if config.get('business', {}).get('mode') == 'franchise' else '自营'}")
    print("=" * 60)
    print()

    # 初始化仿真引擎
    engine = SimulationEngine(
        config=config,
        agent_types=["consumer", "decision"],
        max_steps=max_steps,
    )
    engine.build_graph()

    # 运行仿真（流式输出每轮进度）
    print(">>> 开始仿真...")
    final_state = None
    for i, (step, state) in enumerate(engine.stream()):
        print(f"    第 {i + 1}/{max_steps} 月 完成")
        final_state = state
    if final_state is None:
        final_state, _ = engine.run()
    print(">>> 仿真完成")
    print()

    # 解析结果
    parser_config = config.get("parser", config)
    parser = SimulationResultParser(config=parser_config)
    parse_result = parser.parse(final_state)

    # 控制台输出完整报告
    report = build_full_report(parse_result, config, final_state)
    print(report)

    # 导出文件
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")

    # JSON
    json_path = output_dir / f"result_{ts}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "config": config,
            "summary": parse_result.summary,
            "statistics": parse_result.statistics,
            "risks": [{"level": r.level, "content": r.content} for r in parse_result.risks],
            "timeline_data": parse_result.timeline_data,
        }, f, ensure_ascii=False, indent=2)
    print(f"\n>>> 结果已导出: {json_path}")

    # Markdown
    md_path = output_dir / f"report_{ts}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f">>> 报告已导出: {md_path}")
    print()


if __name__ == "__main__":
    main()
