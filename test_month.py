#!/usr/bin/env python3
"""测试近一个月策略"""
import pickle
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta

# 读取缓存
cache_dir = Path('./data_storage/cache')
cached_df = None

for f in cache_dir.glob('*.pkl'):
    with open(f, 'rb') as file:
        df = pickle.load(file)
    if isinstance(df, pd.DataFrame) and 'date' in df.columns:
        print(f"找到缓存数据: {f.name}")
        print(f"日期范围: {df['date'].min()} ~ {df['date'].max()}")
        cached_df = df
        break

if cached_df is None:
    print("没有找到缓存数据")
    exit(1)

# 筛选近一个月
end_date = datetime(2026, 4, 3)
start_date = end_date - timedelta(days=30)

df = cached_df.copy()
df['date'] = pd.to_datetime(df['date'])
df_month = df[(df['date'] >= start_date) & (df['date'] <= end_date)].copy()
df_month = df_month.sort_values('date').reset_index(drop=True)

print(f"\n近一个月数据: {len(df_month)} 条")
print(f"日期: {df_month['date'].min().date()} ~ {df_month['date'].max().date()}")

# 计算技术指标
df_month['ma5'] = df_month['close'].rolling(5).mean()
df_month['ma20'] = df_month['close'].rolling(20).mean()

# RSI
delta = df_month['close'].diff()
gain = (delta.where(delta > 0, 0)).rolling(14).mean()
loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
rs = gain / loss
df_month['rsi'] = 100 - (100 / (1 + rs))

print("\n" + "="*60)
print("卓易信息 (688258) 近一个月分析")
print("="*60)

# 价格统计
print(f"\n【价格走势】")
print(f"  期初: {df_month['close'].iloc[0]:.2f} 元")
print(f"  期末: {df_month['close'].iloc[-1]:.2f} 元")
print(f"  最高: {df_month['high'].max():.2f} 元")
print(f"  最低: {df_month['low'].min():.2f} 元")
print(f"  涨跌幅: {(df_month['close'].iloc[-1] / df_month['close'].iloc[0] - 1) * 100:+.2f}%")

# 均线分析
last = df_month.iloc[-1]
print(f"\n【均线分析】")
print(f"  MA5:  {last['ma5']:.2f} 元")
print(f"  MA20: {last['ma20']:.2f} 元")
print(f"  当前: {last['close']:.2f} 元")

if last['ma5'] > last['ma20']:
    print(f"  状态: 多头排列 (MA5 > MA20)")
else:
    print(f"  状态: 空头排列 (MA5 < MA20)")

# RSI分析
print(f"\n【RSI分析】")
print(f"  RSI(14): {last['rsi']:.2f}")
if last['rsi'] < 30:
    print(f"  状态: 超卖区 (RSI < 30)，可能反弹")
elif last['rsi'] > 70:
    print(f"  状态: 超买区 (RSI > 70)，可能回调")
else:
    print(f"  状态: 正常区间 (30-70)")

# 模拟交易信号
print(f"\n【模拟交易信号】")
initial_capital = 100000
position = 0
cash = initial_capital
trades = []

for i in range(1, len(df_month)):
    row = df_month.iloc[i]
    prev = df_month.iloc[i-1]

    # 双均线信号
    if pd.notna(row['ma5']) and pd.notna(row['ma20']):
        # 金叉
        if prev['ma5'] <= prev['ma20'] and row['ma5'] > row['ma20'] and position == 0:
            qty = int(cash * 0.95 / row['close'])
            if qty > 0:
                position = qty
                cash -= qty * row['close']
                trades.append({'date': row['date'], 'type': 'MA买入', 'price': row['close'], 'qty': qty})
        # 死叉
        elif prev['ma5'] >= prev['ma20'] and row['ma5'] < row['ma20'] and position > 0:
            cash += position * row['close']
            trades.append({'date': row['date'], 'type': 'MA卖出', 'price': row['close'], 'qty': position})
            position = 0

# 最后清仓
if position > 0:
    cash += position * df_month['close'].iloc[-1]
    position = 0

ma_return = (cash - initial_capital) / initial_capital * 100

# RSI策略
cash = initial_capital
position = 0

for i in range(len(df_month)):
    row = df_month.iloc[i]

    if pd.notna(row['rsi']):
        # RSI超卖买入
        if row['rsi'] < 30 and position == 0:
            qty = int(cash * 0.9 / row['close'])
            if qty > 0:
                position = qty
                cash -= qty * row['close']
                trades.append({'date': row['date'], 'type': 'RSI买入', 'price': row['close'], 'qty': qty})
        # RSI超买卖出
        elif row['rsi'] > 70 and position > 0:
            cash += position * row['close']
            trades.append({'date': row['date'], 'type': 'RSI卖出', 'price': row['close'], 'qty': position})
            position = 0

if position > 0:
    cash += position * df_month['close'].iloc[-1]

rsi_return = (cash - initial_capital) / initial_capital * 100

# 买入持有
buy_hold_return = (df_month['close'].iloc[-1] / df_month['close'].iloc[0] - 1) * 100

print(f"\n【策略对比 (初始资金 10万)】")
print(f"  双均线策略: {ma_return:+.2f}%")
print(f"  RSI策略:    {rsi_return:+.2f}%")
print(f"  买入持有:   {buy_hold_return:+.2f}%")

# 显示最近交易
print(f"\n【最近交易记录】")
for t in trades[-5:]:
    print(f"  {t['date'].strftime('%Y-%m-%d')} {t['type']} {t['qty']}股 @ {t['price']:.2f}")
