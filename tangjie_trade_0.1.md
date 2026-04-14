# 隔夜持股T+1量化策略 - Python伪代码
# 适配主流量化框架（聚宽/米筐/VNPY/自定义Qoder系统）
# 核心：尾盘买→次日卖，纯规则化，无主观判断

import pandas as pd
import numpy as np

# ===================== 1. 策略核心参数（可直接配置修改）=====================
STRATEGY_PARAMS = {
    # 时间规则
    "buy_start_time": "14:50:00",    # 买入开始时间
    "buy_end_time": "15:00:00",      # 买入结束时间
    "sell_start_time": "09:30:00",   # 卖出开始时间
    "sell_end_time": "10:00:00",     # 卖出结束时间（强制清仓）
    # 选股参数
    "min_daily_amount": 100000000,   # 日均成交额≥1亿
    "min_turnover": 3,               # 换手率≥3%
    "rise_range": (3, 7),            # 当日涨幅3%-7%
    "min_volume_ratio": 1.2,         # 量比≥1.2
    "new_stock_days": 60,            # 剔除上市＜60天次新
    # 交易规则
    "single_position": 0.1,          # 单票仓位10%
    "max_hold_num": 5,               # 最大持仓5只
    "total_position_limit": 0.5,     # 总仓位≤50%
    # 止盈止损
    "take_profit": 0.03,             # 止盈3%
    "stop_loss": -0.02,              # 止损-2%
    "break_even": 0.00,              # 保本线
}

# ===================== 2. 全局黑名单过滤（每日盘前执行）=====================
def filter_black_list(stock_list):
    """过滤ST、退市、次新、停牌、一字板"""
    valid_stocks = []
    for stock in stock_list:
        # 1. 剔除ST/*ST/退市
        if "ST" in stock.name or "退" in stock.name:
            continue
        # 2. 剔除上市＜60天次新
        if (datetime.now() - stock.list_date).days < STRATEGY_PARAMS["new_stock_days"]:
            continue
        # 3. 剔除停牌/一字板
        if stock.is_suspended or stock.is_limit_up:
            continue
        valid_stocks.append(stock)
    return valid_stocks

# ===================== 3. 量化选股逻辑（尾盘执行）=====================
def select_stocks(valid_stocks):
    """技术面选股，返回目标持仓列表"""
    target_list = []
    for stock in valid_stocks:
        # 1. 流动性过滤
        if stock.daily_amount < STRATEGY_PARAMS["min_daily_amount"]:
            continue
        if stock.turnover < STRATEGY_PARAMS["min_turnover"]:
            continue
        # 2. 涨幅过滤
        rise_pct = stock.today_rise_pct
        if not (STRATEGY_PARAMS["rise_range"][0] <= rise_pct <= STRATEGY_PARAMS["rise_range"][1]):
            continue
        # 3. 量能过滤
        if stock.volume_ratio < STRATEGY_PARAMS["min_volume_ratio"]:
            continue
        # 4. 均线多头（MA5>MA10>MA20）
        ma5 = stock.ma(5)
        ma10 = stock.ma(10)
        ma20 = stock.ma(20)
        if not (ma5 > ma10 > ma20):
            continue
        # 5. 加入目标池
        target_list.append(stock)
        # 限制最大持仓数
        if len(target_list) >= STRATEGY_PARAMS["max_hold_num"]:
            break
    return target_list

# ===================== 4. 买入执行逻辑 =====================
def buy_execution(target_list, cash):
    """尾盘自动买入，仓位均分"""
    if not target_list:
        return
    # 单票可用资金
    per_stock_cash = cash * STRATEGY_PARAMS["single_position"]
    for stock in target_list:
        # 仓位控制：总仓位不超50%
        if get_total_position() >= STRATEGY_PARAMS["total_position_limit"]:
            break
        # 现价买入
        buy_price = stock.last_price
        buy_volume = int(per_stock_cash / buy_price / 100) * 100  # 100股整数倍
        if buy_volume > 0:
            order_buy(stock.code, buy_price, buy_volume)
            # 记录持仓成本
            hold_position[stock.code] = {"cost": buy_price, "volume": buy_volume}

# ===================== 5. 卖出执行逻辑（次日必卖）=====================
def sell_execution():
    """早盘自动卖出，强制清仓+止盈止损"""
    if not hold_position:
        return
    for code, pos in hold_position.items():
        stock = get_stock(code)
        current_price = stock.last_price
        cost_price = pos["cost"]
        profit_pct = (current_price - cost_price) / cost_price

        # 1. 止盈：≥3%
        if profit_pct >= STRATEGY_PARAMS["take_profit"]:
            order_sell(code, current_price, pos["volume"])
            del hold_position[code]
            continue
        # 2. 止损：≤-2%
        if profit_pct <= STRATEGY_PARAMS["stop_loss"]:
            order_sell(code, current_price, pos["volume"])
            del hold_position[code]
            continue
        # 3. 平开/小低开：反弹保本卖
        if STRATEGY_PARAMS["stop_loss"] < profit_pct < STRATEGY_PARAMS["take_profit"]:
            if current_price >= cost_price:
                order_sell(code, current_price, pos["volume"])
                del hold_position[code]
                continue
        # 4. 强制清仓：10点前全部卖出
        if current_time >= STRATEGY_PARAMS["sell_end_time"]:
            order_sell(code, current_price, pos["volume"])
            del hold_position[code]

# ===================== 6. 主策略循环（每日执行）=====================
def strategy_main():
    global hold_position
    hold_position = {}  # 持仓字典
    # 盘前：过滤黑名单
    all_stocks = get_all_stocks()
    valid_stocks = filter_black_list(all_stocks)

    # 每日时间判断
    if is_trading_day():
        current_time = get_current_time()
        cash = get_cash()

        # 阶段1：尾盘买入（14:50-15:00）
        if STRATEGY_PARAMS["buy_start_time"] <= current_time <= STRATEGY_PARAMS["buy_end_time"]:
            # 无持仓才买入
            if not hold_position:
                target_stocks = select_stocks(valid_stocks)
                buy_execution(target_stocks, cash)

        # 阶段2：次日早盘卖出（9:30-10:00）
        if STRATEGY_PARAMS["sell_start_time"] <= current_time <= STRATEGY_PARAMS["sell_end_time"]:
            sell_execution()

# ===================== 7. 风控兜底（系统级）=====================
def risk_control():
    """系统级风控，强制触发"""
    # 1. 大盘破位空仓：指数跌幅＞1.5%
    if get_index_drop() > 1.5:
        clear_all_position()
    # 2. 跌停数＞15，空仓
    if get_limit_down_num() > 15:
        clear_all_position()
    # 3. 单笔亏损超2%，强制平仓
    for code, pos in hold_position.items():
        profit_pct = (get_stock(code).last_price - pos["cost"]) / pos["cost"]
        if profit_pct < STRATEGY_PARAMS["stop_loss"]:
            order_sell(code, get_stock(code).last_price, pos["volume"])
            del hold_position[code]

# 启动策略
if __name__ == "__main__":
    strategy_main()
    risk_control()

---

### 适配说明
1. **接口替换**：把`get_stock`/`order_buy`/`order_sell`等函数，替换成你量化系统的原生API即可
2. **参数调优**：直接改`STRATEGY_PARAMS`里的数值，适配你的交易风格
3. **回测适配**：可直接接入回测框架，按每日尾盘/次日早盘循环跑回测
4. **精简版**：如果需要极简版代码（去掉注释，纯核心逻辑），我可以再压缩一版