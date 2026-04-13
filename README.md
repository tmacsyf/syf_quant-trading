# 智能量化交易系统

一个支持 A股、港股、美股 的 Python 量化交易框架，适合个人投资者进行策略研发和回测。

---

## 快速开始（3分钟上手）

### 1. 安装依赖

```bash
cd quant-trading
pip3 install akshare yfinance pandas numpy
```

### 2. 运行回测示例

```bash
python examples/demo_backtest.py
```

### 3. 命令行运行回测

```bash
# 双均线策略回测平安银行
python main.py --strategy ma --symbol 000001 --start 2023-01-01 --end 2024-01-01

# RSI均值回归策略
python main.py --strategy mean_reversion --symbol 000001
```

---

## 系统能做什么？

| 功能 | 说明 |
|------|------|
| **数据获取** | 自动获取 A股/港股/美股 历史行情数据 |
| **技术指标** | 自动计算 MA、MACD、RSI、布林带、ATR 等 |
| **策略回测** | 模拟真实交易，计算收益率、夏普比率、最大回撤 |
| **策略开发** | 提供基础策略模板，方便开发自己的策略 |

---

## 项目结构说明

```
quant-trading/
├── data/              # 数据相关
│   ├── fetcher.py     # 获取股票数据（A股/港股/美股）
│   ├── cache.py       # 数据缓存，避免重复下载
│   └── preprocessor.py # 数据清洗 + 计算技术指标
│
├── backtest/          # 回测引擎
│   └── engine.py      # 模拟买卖、计算收益
│
├── strategy/          # 交易策略
│   ├── base.py        # 策略基类（开发新策略从这里继承）
│   └── moving_average.py # 双均线策略 + RSI策略
│
├── examples/          # 示例代码
│   └── demo_backtest.py  # 回测演示
│
└── main.py            # 命令行入口
```

---

## 内置策略说明

### 1. 双均线策略 (MovingAverageCross)

**原理**：短期均线上穿长期均线买入，下穿卖出

```python
# 参数
fast_period = 5    # 短期均线（5日）
slow_period = 20   # 长期均线（20日）

# 信号
金叉（5日 > 20日）→ 买入
死叉（5日 < 20日）→ 卖出
```

### 2. RSI均值回归策略 (MeanReversion)

**原理**：RSI超卖时买入，超买时卖出

```python
# 参数
rsi_period = 14    # RSI计算周期
oversold = 30      # 超卖阈值
overbought = 70    # 超买阈值

# 信号
RSI < 30 → 买入（超卖，可能反弹）
RSI > 70 → 卖出（超买，可能回调）
```

---

## 如何开发自己的策略？

### 步骤1：继承 BaseStrategy

```python
from strategy.base import BaseStrategy

class MyStrategy(BaseStrategy):
    def __init__(self):
        super().__init__("MyStrategy")
    
    def on_data(self, data):
        # data 包含所有股票的历史数据
        for symbol, df in data.items():
            # df 是 DataFrame，包含 open/high/low/close/volume 和技术指标
            
            # 获取当前持仓
            position = self.get_position(symbol)
            has_position = position.get('quantity', 0) > 0
            
            # 你的交易逻辑
            if 买入信号 and not has_position:
                self.buy(symbol, percent=0.95)  # 用95%资金买入
            
            elif 卖出信号 and has_position:
                self.sell_all(symbol)  # 清仓
```

### 步骤2：运行回测

```python
from data import DataFetcher, DataPreprocessor
from backtest import BacktestEngine

# 获取数据
fetcher = DataFetcher()
df = fetcher.get_a_share_daily('000001', '2023-01-01', '2024-01-01')

# 预处理
preprocessor = DataPreprocessor()
df = preprocessor.prepare_for_backtest(df)

# 运行回测
engine = BacktestEngine(initial_capital=100000)
engine.add_data('000001', df)
engine.set_strategy(MyStrategy())
results = engine.run()

# 查看结果
print(f"收益率: {results['summary']['total_return']*100:.2f}%")
```

---

## 回测结果解读

运行回测后会输出以下指标：

| 指标 | 含义 | 参考标准 |
|------|------|----------|
| **总收益率** | 整个回测期间的收益 | > 0 表示盈利 |
| **年化收益率** | 折算到一年的收益 | 一般 > 10% 较好 |
| **夏普比率** | 收益与风险的比值 | > 1 较好，> 2 优秀 |
| **最大回撤** | 从高点到低点的最大亏损 | 越小越好，一般 < 20% |
| **交易次数** | 买卖的总次数 | 反映策略活跃度 |

---

## 数据源说明

| 市场 | 数据源 | 代码示例 |
|------|--------|----------|
| A股 | AKShare | `fetcher.get_a_share_daily('000001')` |
| 港股 | AKShare | `fetcher.get_hk_stock_daily('00700')` |
| 美股 | Yahoo Finance | `fetcher.get_us_stock_daily('AAPL')` |

**注意**：首次运行需要联网下载数据，之后会自动缓存到本地。

---

## 常见问题

### Q: 为什么回测结果和实际交易有差异？

A: 回测是理想化模拟，实际交易还有以下因素：
- 滑点（下单价格和成交价格的差异）
- 流动性（大单可能无法一次成交）
- 市场冲击（大额交易影响价格）

### Q: 如何优化策略？

A: 可以尝试：
1. 调整策略参数（如均线周期）
2. 添加风控规则（止损止盈）
3. 多策略组合
4. 加入更多技术指标

### Q: 能直接用于实盘交易吗？

A: 目前只能回测，实盘需要对接券商 API（如富途、Interactive Brokers），需要额外开发。

---

## 技术栈

- **Python 3.10+**
- **pandas**: 数据处理
- **numpy**: 数值计算
- **akshare**: A股/港股数据
- **yfinance**: 美股数据

---

## 免责声明

本系统仅供学习研究使用，不构成投资建议。股市有风险，投资需谨慎。
