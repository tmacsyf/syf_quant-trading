#!/usr/bin/env python3
"""唐杰策略 - 科创板精选（高涨幅版）"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from strategy import TangjieStockSelector
from data import DataFetcher
from datetime import datetime, timedelta
import akshare as ak


def get_kcb_symbols():
    """自动获取科创板全部股票代码"""
    try:
        df = ak.stock_info_sh_name_code(symbol='科创板')
        symbols = df['证券代码'].tolist()
        return sorted(symbols)
    except Exception as e:
        print(f'获取科创板股票列表失败: {e}')
        print('将使用默认股票池（40只）')
        return [
            '688981', '688012', '688008', '688396', '688599',
            '688169', '688036', '688111', '688561', '688009',
            '688185', '688180', '688276', '688520', '688266',
            '688005', '688116', '688006', '688339', '688778',
            '688188', '688200', '688301', '688686', '688017',
            '688256', '688787', '688327', '688207', '688292',
            '688019', '688122', '688234', '688072', '688082',
            '688220', '688153', '688409', '688223', '688295',
        ]


symbols = get_kcb_symbols()

print('=' * 70)
print('唐杰策略 - 科创板精选（高涨幅版）')
print(f'日期: {datetime.now().strftime("%Y-%m-%d")}')
print('=' * 70)

print('\n【策略参数】')
print(f'  股票池: 科创板（{len(symbols)}只）')
print('  涨幅条件: > 7%（强势股）')
print('  量比: ≥ 1.2')
print('  均线: MA5 > MA10 > MA20')
print('  成交额: ≥ 1亿')
print('  最大持仓: 2只')
print('  单票金额: 10万元')
print('  总资金: 20万元')

print(f'\n股票池: {len(symbols)} 只科创板股票')

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
        if i % 50 == 0:
            print(f'  [{i}/{len(symbols)}] 已获取 {len(stock_data)} 只')
    except Exception:
        pass

print(f'\n成功获取 {len(stock_data)} 只股票数据')

if len(stock_data) < 5:
    print('\n错误: 数据获取不足，无法选股')
    sys.exit(1)

# 选股 - 使用自定义参数
print('\n[2/2] 执行选股...')
selector = TangjieStockSelector({
    'rise_range': (7, 20),      # 涨幅 > 7%
    'min_volume_ratio': 1.2,     # 量比 ≥ 1.2
    'min_daily_amount': 100000000,  # 成交额 ≥ 1亿
    'max_hold_num': 2,           # 最多2只
    'single_position': 0.5,      # 单票50%（10万/20万）
})

selected = selector.select(stock_data)

if selected.empty:
    print('=' * 70)
    print('今日无符合选股条件的科创板股票')
    print('=' * 70)
    print('\n可能原因:')
    print('  • 今日科创板整体涨幅不大（未超过7%）')
    print('  • 强势股量能不足')
    print('  • 均线多头排列的股票较少')
    print('\n建议:')
    print('  • 关注盘中涨幅超过7%的科创板股票')
    print('  • 或等待市场出现强势板块')
else:
    print(f'\n选中 {len(selected)} 只科创板股票:')
    print('=' * 70)
    
    for i, (idx, row) in enumerate(selected.head(2).iterrows(), 1):
        print(f"\n【{i}】{row['symbol']}")
        print(f"  收盘价:    {row['close']:.2f} 元")
        print(f"  今日涨幅:  {row['rise_pct']:.2f}% {'🔥' if row['rise_pct'] > 10 else '✓'}")
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
        
        # 买入数量计算
        price = row['close']
        quantity = int(100000 / price / 100) * 100  # 10万元，整手
        actual_amount = quantity * price
        print(f"  建议买入:  {quantity}股 ({actual_amount/10000:.2f}万元)")
    
    print('\n' + '=' * 70)
    print('今日操作建议:')
    print('=' * 70)
    
    top2 = selected.head(2)
    print(f"\n建议关注前 {len(top2)} 只科创板股票:")
    for i, (idx, row) in enumerate(top2.iterrows(), 1):
        quantity = int(100000 / row['close'] / 100) * 100
        print(f"\n  {i}. {row['symbol']}")
        print(f"     涨幅: {row['rise_pct']:.2f}% | 量比: {row['volume_ratio']:.2f}")
        print(f"     买入: {quantity}股 @ {row['close']:.2f}元")
        print(f"     金额: {quantity * row['close'] / 10000:.2f}万元")
    
    print("\n" + "-" * 70)
    print("买入规则:")
    print("  • 时间: 14:50 - 15:00（尾盘）")
    print("  • 仓位: 每只10万元，共20万元")
    print("  • 数量: 最多2只")
    
    print("\n卖出规则:")
    print("  • 止盈: +3%")
    print("  • 止损: -2%")
    print("  • 强制清仓: 次日10:00前")
    
    print("\n风险提示:")
    print("  ⚠ 涨幅>7%属于强势股，波动较大")
    print("  ⚠ 科创板涨跌幅限制为20%，风险高于主板")
    print("  ⚠ 建议严格控制止损，避免大幅回撤")

print('\n' + '=' * 70)
print('免责声明: 本选股结果仅供学习研究，不构成投资建议。')
print('股市有风险，投资需谨慎。')
print('=' * 70)
