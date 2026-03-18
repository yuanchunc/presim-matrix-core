# 奶茶店开店预演 Demo

**25万开奶茶店，从加盟到闭店6个月预演**

预演沙盘的核心爆款案例，对标 MiroFish 的红楼梦演示。通过多智能体仿真，还原真实经营的连锁反应，呈现**理想测算 vs 真实预演**的强烈反差。

## 场景介绍

- **理想测算**（加盟商宣传）：月赚 2 万，半年回本
- **真实预演**：约 90% 概率 6 个月现金流断裂闭店，累计亏损约 22 万

仿真涵盖：加盟品牌方、房东、供应商、员工、5 家竞品、多种消费者类型，以及商圈客流规律、淡旺季、竞品促销分流等真实因素。

## 快速开始

### 1. 环境准备

```bash
# 进入项目根目录
cd presim-matrix-core

# 安装依赖
pip install -r requirements.txt

# 可选：配置大模型 API Key（用于增强分析）
cp examples/milk_tea_shop/.env.example examples/milk_tea_shop/.env
# 编辑 .env，填入 OPENAI_API_KEY 或 GOOGLE_API_KEY 等
```

### 2. 一键运行

```bash
python examples/milk_tea_shop/run_simulation.py
```

无需修改任何代码，即可跑通完整 6 个月仿真。

### 3. 查看结果

- **控制台**：实时输出仿真进度和完整 Markdown 报告
- **output/**：自动导出 JSON 和 Markdown 文件，便于保存和分享

## 配置说明

所有参数均在 `config.yaml` 中，可自由修改：

| 配置项 | 说明 | 示例 |
|--------|------|------|
| `capital.initial` | 启动资金 | 250000 |
| `business.mode` | 经营模式 | franchise / self_owned |
| `business.franchise_fee` | 加盟费 | 50000 |
| `location.city` | 城市 | 杭州 |
| `location.rent_monthly` | 月租金 | 15000 |
| `pricing.base_price` | 基础单价 | 16 |
| `simulation.steps` | 仿真月数 | 6 |

## 参数修改示例

### 调整启动资金

```yaml
capital:
  initial: 300000  # 改为 30 万
```

### 改为自营模式

```yaml
business:
  mode: self_owned
  franchise_fee: 0
```

### 延长仿真周期

```yaml
simulation:
  steps: 12  # 12 个月
```

## 结果解读

### 核心指标

- **total_profit**：累计利润（负值=亏损）
- **final_cash_flow**：6 个月后剩余现金流
- **break_even_step**：盈亏平衡月（-1 表示未达到）

### 风险提示

- **HIGH**：现金流断裂、无法支付成本
- **MEDIUM**：连续亏损、客流骤降
- **LOW**：无明显风险，建议持续关注

### 理想 vs 真实对比表

报告中的对比表直观展示加盟商宣传口径与真实预演的差距，帮助决策者理性评估开店风险。

## 基于此示例扩展

1. 复制 `config.yaml` 和 `run_simulation.py`
2. 修改 `config.yaml` 中的场景参数
3. 如需自定义智能体，在 `run_simulation.py` 中通过 `registry.register_agent_class()` 注册
4. 运行 `python run_simulation.py`

## 常见问题

**Q: 没有配置 API Key 能运行吗？**  
A: 可以。本 Demo 不强制依赖大模型，解析器会根据配置生成预演数据。

**Q: 如何导出报告？**  
A: 运行后自动在 `output/` 目录生成 `result_*.json` 和 `report_*.md`。

**Q: 如何修改为其他城市/行业？**  
A: 修改 `config.yaml` 中的 `location`、`pricing`、`costs` 等，并确保 `scene` 与解析器支持的场景匹配。
