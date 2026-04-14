#!/usr/bin/env python3
"""测试唐杰策略"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from strategy import TangjieStockSelector
from data import DataFetcher
from datetime import datetime, timedelta

print('=' * 70)
print('唐杰隔夜持股T+1策略 - 今日选股测试')
print('=' * 70)

# 测试选股
symbols = ['000001', '000002', '600519', '000858', '002594']
print(f'\n股票池: {len(symbols)} 只股票')

fetcher = DataFetcher()
stock_data = {}

end_date = datetime.now().strftime('%Y%m%d')
start_date = (datetime.now() - timedelta(days=60)).strftime('%Y%m%d')

print('\n获取数据...')
for symbol in symbols:
    try:
        df = fetcher.get_a_share_daily(symbol, start_date, end_date)
        if not df.empty and len(df) >= 20:
            stock_data[symbol] = df
            print(f'  {symbol} - {len(df)} 条数据')
    except Exception as e:
        print(f'  {symbol} - 失败: {e}')

print(f'\n成功获取 {len(stock_data)} 只股票数据')

# 选股
print('\n执行选股...')
selector = TangjieStockSelector()
selected = selector.select(stock_data)

if selected.empty:
    print('\n今日无符合选股条件的股票')
else:
    print(f'\n选中 {len(selected)} 只股票:')
    print('-' * 70)
    for idx, row in selected.iterrows():
        print(f"\n【{row['symbol']}】")
        print(f"  收盘价: {row['close']:.2f} 元")
        print(f"  涨幅: {row['rise_pct']:.2f}%")
        print(f"  量比: {row['volume_ratio']:.2f}")
        print(f"  成交额: {row['amount']/100000000:.2f} 亿元")

print('\n' + '=' * 70)
print('测试完成!')
print('=' * 70)
