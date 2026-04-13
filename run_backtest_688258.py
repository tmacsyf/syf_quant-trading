#!/usr/bin/env python3
"""卓易信息(688258)近一个月回测"""
import sys
sys.path.insert(0, '.')

from data import DataFetcher, DataPreprocessor
from backtest import BacktestEngine
from strategy import MeanReversionStrategy, MovingAverageCrossStrategy
from datetime import datetime

print('=' * 60)
print('量化交易系统 - 卓易信息(688258) 回测')
print('时间范围: 2026-03-03 至 2026-04-03')
print('=' * 60)

print('\n[1/4] 获取数据: 688258 (a_share)...')
fetcher = DataFetcher()
df = fetcher.get_a_share_daily('688258', '20260303', '20260403')
print(f'  从数据源获取 {len(df)} 条数据')
print(f'  日期范围: {df["date"].min()} 至 {df["date"].max()}')

print('\n[2/4] 数据预处理...')
preprocessor = DataPreprocessor()
df = preprocessor.prepare_for_backtest(df)
print(f'  预处理后: {len(df)} 条数据')

# 显示价格统计
print(f'\n  价格统计:')
print(f'    开盘价范围: {df["open"].min():.2f} - {df["open"].max():.2f}')
print(f'    收盘价范围: {df["close"].min():.2f} - {df["close"].max():.2f}')
print(f'    期间涨跌: {(df["close"].iloc[-1] / df["close"].iloc[0] - 1) * 100:+.2f}%')

print('\n[3/4] 创建策略: RSI Mean Reversion')
strategy = MeanReversionStrategy(rsi_period=14, oversold=30, overbought=70)

print('\n[4/4] 运行回测...')
engine = BacktestEngine(initial_capital=100000)
engine.add_data('688258', df)
engine.set_strategy(strategy)

results = engine.run()

print('\n' + '=' * 60)
print('回测结果')
print('=' * 60)

summary = results['summary']
print(f"初始资金:     {summary['initial_capital']:,.2f} 元")
print(f"最终资金:     {summary['final_value']:,.2f} 元")
print(f"总收益率:     {summary['total_return']*100:+.2f}%")
print(f"年化收益率:   {summary.get('annualized_return', 0)*100:+.2f}%")
print(f"夏普比率:     {summary.get('sharpe_ratio', 0):.2f}")
print(f"最大回撤:     {summary.get('max_drawdown', 0)*100:.2f}%")
print(f"交易次数:     {summary['total_trades']}")

trades_df = results['trades']
if not trades_df.empty:
    print(f'\n交易明细:')
    print(trades_df.to_string(index=False))
else:
    print('\n无交易记录')

# 每日持仓价值
print('\n' + '-' * 60)
print('每日持仓变化')
print('-' * 60)
equity_df = results['equity_curve']
if not equity_df.empty:
    print(equity_df[['timestamp', 'total_value', 'cash', 'positions_value']].to_string(index=False))

print('\n' + '=' * 60)
print('回测完成!')
print('=' * 60)
