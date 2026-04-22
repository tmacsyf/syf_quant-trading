#!/usr/bin/env python3
"""唐杰策略 - 今日选股"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from strategy import TangjieStockSelector
from data import DataFetcher
from datetime import datetime, timedelta

# 热门股票池
symbols = [
    # 金融
    '000001', '600000', '600036', '601398', '601318',
    # 科技
    '000725', '002415', '002230', '000063', '600498',
    # 消费
    '600519', '000858', '600887', '002594', '000333',
    # 医药
    '600276', '000538', '600436', '300760', '603259',
    # 新能源
    '300750', '601012', '600438', '002460', '300274',
    # 半导体
    '688981', '688012', '688008', '600584', '002049',
    # 其他
    '600009', '600115', '601888', '600030', '000768',
    '002352', '600104', '601668', '601766', '600031',
    '000651', '000100', '600050', '601186', '601088',
    '600028', '601857', '600938', '601728', '600941',
    '688111', '688036', '688169', '688599', '688396',
    # 近期热门
    '002371', '002156', '600171', '300046', '300672',
    '300418', '002517', '002624', '300413', '300251',
]

print('=' * 70)
print('唐杰隔夜持股T+1策略 - 今日选股')
print(f'日期: {datetime.now().strftime("%Y-%m-%d")}')
print('=' * 70)

print(f'\n股票池: {len(symbols)} 只股票')

fetcher = DataFetcher()
stock_data = {}

end_date = datetime.now().strftime('%Y%m%d')
start_date = (datetime.now() - timedelta(days=60)).strftime('%Y%m%d')

print('\n[1/2] 获取数据...')
for i, symbol in enumerate(symbols, 1):
    try:
        df = fetcher.get_a_share_daily(symbol, start_date, end_date)
        if not df.empty and len(df) >= 20:
            stock_data[symbol] = df
            if i <= 10 or i % 10 == 0:
                print(f'  [{i}/{len(symbols)}] {symbol} - {len(df)} 条数据')
    except Exception as e:
        if i <= 5:
            print(f'  [{i}/{len(symbols)}] {symbol} - 失败')

print(f'\n成功获取 {len(stock_data)} 只股票数据')

if len(stock_data) < 10:
    print('\n错误: 数据获取不足，无法选股')
    sys.exit(1)

# 选股
print('\n[2/2] 执行选股...')
print('选股条件:')
print('  - 涨幅: 3% - 7%')
print('  - 量比: ≥1.2')
print('  - 均线: MA5 > MA10 > MA20')
print('  - 成交额: ≥1亿')
print()

selector = TangjieStockSelector()
selected = selector.select(stock_data)

if selected.empty:
    print('=' * 70)
    print('今日无符合选股条件的股票')
    print('=' * 70)
    print('\n可能原因:')
    print('  • 今日市场整体涨幅不在3-7%区间')
    print('  • 符合条件的股票量能不足')
    print('  • 均线多头排列的股票较少')
    print('\n建议: 放宽选股条件或等待更好的入场时机')
else:
    print(f'选中 {len(selected)} 只股票:')
    print('=' * 70)
    
    for i, (idx, row) in enumerate(selected.iterrows(), 1):
        print(f"\n【{i}】{row['symbol']}")
        print(f"  收盘价:    {row['close']:.2f} 元")
        print(f"  今日涨幅:  {row['rise_pct']:.2f}%")
        print(f"  量比:      {row['volume_ratio']:.2f}")
        print(f"  成交额:    {row['amount']/100000000:.2f} 亿元")
        print(f"  均线系统:")
        print(f"    MA5:  {row['ma5']:.2f}")
        print(f"    MA10: {row['ma10']:.2f}")
        print(f"    MA20: {row['ma20']:.2f}")
        
        # 判断均线形态
        if row['ma5'] > row['ma10'] > row['ma20']:
            print(f"    形态: 多头排列 ✓")
        
        # 计算距离均线的位置
        above_ma5 = (row['close'] - row['ma5']) / row['ma5'] * 100
        print(f"  技术位置:  高于MA5 {above_ma5:.2f}%")
    
    print('\n' + '=' * 70)
    print('操作建议:')
    print('=' * 70)
    
    top5 = selected.head(5)
    print(f"\n建议关注前 {len(top5)} 只（按涨幅排序）:")
    for i, (idx, row) in enumerate(top5.iterrows(), 1):
        print(f"  {i}. {row['symbol']} - 涨幅{row['rise_pct']:.2f}%, 量比{row['volume_ratio']:.2f}")
    
    print("\n买入规则:")
    print("  • 时间: 14:50 - 15:00（尾盘）")
    print("  • 仓位: 单票不超过10%")
    print("  • 数量: 最多5只")
    
    print("\n卖出规则:")
    print("  • 止盈: +3%")
    print("  • 止损: -2%")
    print("  • 强制清仓: 次日10:00前")

print('\n' + '=' * 70)
print('免责声明: 本选股结果仅供学习研究，不构成投资建议。')
print('股市有风险，投资需谨慎。')
print('=' * 70)
