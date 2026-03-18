"""
预演沙盘 PreSim Matrix - Streamlit 可视化 Demo

3 步完成奶茶店开店预演：配置参数 → 一键启动 → 查看结果
对标 MiroFish 在线体验，零门槛体验「预演式决策」核心价值。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# 项目根目录
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# 加载 .env（若存在）
_env_paths = [
    ROOT / "examples" / "milk_tea_shop" / ".env",
    ROOT / ".env",
]
for _p in _env_paths:
    if _p.exists():
        with open(_p) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
        break

import streamlit as st

from ui.components.config_panel import render_config_panel, render_export_config
from ui.components.conclusion_panel import render_conclusion_panel
from ui.components.result_charts import render_result_charts
from ui.components.risk_panel import render_risk_panel
from ui.components.timeline_panel import render_timeline_panel
from ui.components.report_panel import render_report_panel
from ui.components.simulation_runner import run_simulation
from ui.utils import build_config_from_params


# =============================================================================
# 页面配置
# =============================================================================

st.set_page_config(
    page_title="预演沙盘 - 奶茶店开店预演",
    page_icon="🧋",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =============================================================================
# 初始化 Session State
# =============================================================================

def _init_session_state():
    if "parse_result" not in st.session_state:
        st.session_state["parse_result"] = None
    if "config" not in st.session_state:
        st.session_state["config"] = None
    if "error" not in st.session_state:
        st.session_state["error"] = None


_init_session_state()


# =============================================================================
# 主布局
# =============================================================================

# 标题
st.title("🧋 奶茶店开店预演")
st.markdown(
    "**25万开奶茶店，从加盟到闭店6个月预演** · "
    "理想测算月赚2万半年回本 vs 真实预演 90% 概率现金流断裂"
)
st.divider()

# 左侧栏：参数配置
with st.sidebar:
    st.header("⚙️ 参数配置")
    params = render_config_panel()
    render_export_config(params)
    st.divider()

# 主区域：启动按钮 + 进度 + 结论
col_main, col_btn = st.columns([3, 1])
with col_btn:
    start_clicked = st.button(
        "🚀 一键启动仿真",
        type="primary",
        use_container_width=True,
    )

if start_clicked:
    st.session_state["error"] = None
    st.session_state["parse_result"] = None
    st.session_state["config"] = None

    progress_placeholder = st.empty()
    status_placeholder = st.empty()

    def _on_progress(step: int, max_steps: int):
        with progress_placeholder.container():
            p = step / max_steps if max_steps else 0
            st.progress(min(1.0, p))
            st.caption(f"第 {step} / {max_steps} 月 完成")

    with status_placeholder.container():
        st.info("仿真进行中，请稍候…")

    try:
        final_state, parse_result, err = run_simulation(params, progress_callback=_on_progress)
        if err:
            st.session_state["error"] = err
        else:
            st.session_state["parse_result"] = parse_result
            st.session_state["config"] = build_config_from_params(params)
    except Exception as e:
        st.session_state["error"] = str(e)
    finally:
        progress_placeholder.empty()
        status_placeholder.empty()
    st.rerun()

# 错误提示
if st.session_state.get("error"):
    st.error(f"❌ 仿真执行失败：{st.session_state['error']}")
    st.caption("请检查参数配置是否正确，或查看控制台错误信息")

# 核心结论看板
parse_result = st.session_state.get("parse_result")
config = st.session_state.get("config") or build_config_from_params(params)
render_conclusion_panel(parse_result, config)

st.divider()

# 详细结果：标签页
if parse_result is not None:
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 时序图表",
        "📅 关键节点",
        "⚠️ 风险提示",
        "📄 完整报告",
    ])
    with tab1:
        render_result_charts(parse_result)
    with tab2:
        render_timeline_panel(parse_result)
    with tab3:
        render_risk_panel(parse_result)
    with tab4:
        render_report_panel(parse_result, config)

# 底部：使用说明
with st.expander("📖 使用说明", expanded=False):
    st.markdown("""
    1. **左侧** 填写或修改参数，默认值为经典案例（25万加盟、杭州写字楼、6个月）
    2. **点击「一键启动仿真」** 开始预演
    3. **查看结果**：核心结论、时序图表、风险提示、完整报告

    - 无需配置 API Key 即可运行
    - 支持导出 Markdown 报告
    - 修改参数可模拟不同开店方案
    """)
