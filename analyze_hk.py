#!/usr/bin/env python3
"""港股阿里巴巴行情分析"""
import sys
import io
import urllib.request
import re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 获取港股数据 (rt_hk前缀，05位代码补零)
url = 'http://hq.sinajs.cn/list=rt_hk09988'
req = urllib.request.Request(url, headers={
    'Referer': 'http://finance.sina.com.cn',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
})
resp = urllib.request.urlopen(req, timeout=10)
text = resp.read().decode('gbk')

match = re.search(r'"(.*)"', text)
if not match:
    print("获取数据失败")
    sys.exit(1)

fields = match.group(1).split(',')

# 港股新浪字段解析:
# [0] 英文名, [1] 中文名, [2] 昨收, [3] 今开, [4] 最高, [5] 最低
# [6] 现价, [7] 涨跌额, [8] 涨跌幅, [9] 买一, [10] 卖一
# [11] 成交额, [12] 成交量(股), [13] 市盈率, [14] ?, [15] 52周最高, [16] 52周最低
# [17] 日期, [18] 时间

name_en  = fields[0]
name_cn  = fields[1]
pre_close = float(fields[2])
open_p   = float(fields[3])
high     = float(fields[4])
low      = float(fields[5])
price    = float(fields[6])
change_amt = float(fields[7])
change_pct = float(fields[8])
bid1     = float(fields[9])
ask1     = float(fields[10])
amount   = float(fields[11])
volume   = int(fields[12])
pe_ratio = float(fields[13]) if fields[13] else 0
week52_high = float(fields[15]) if fields[15] else 0
week52_low  = float(fields[16]) if fields[16] else 0
date_str = fields[17]
time_str = fields[18]

# 均价
avg_price = amount / volume if volume > 0 else price
# 振幅
amplitude = (high - low) / pre_close * 100 if pre_close else 0
# 价格位置(今日区间)
day_position = (price - low) / (high - low) * 100 if high != low else 50
# 52周位置
week52_pos = (price - week52_low) / (week52_high - week52_low) * 100 if week52_high != week52_low else 50

print('=' * 60)
print(f'阿里巴巴 {name_en} ({name_cn})')
print(f'港股代码: 9988.HK  更新: {date_str} {time_str}')
print('=' * 60)

print('\n【实时行情】')
sign = '+' if change_amt >= 0 else ''
print(f'  现价:     {price:.2f} 港币   涨跌: {sign}{change_pct:.2f}% ({sign}{change_amt:.2f})')
print(f'  今开:     {open_p:.2f}   昨收: {pre_close:.2f}')
print(f'  最高:     {high:.2f}   最低: {low:.2f}')
print(f'  振幅:     {amplitude:.2f}%')
print(f'  买一:     {bid1:.2f}   卖一: {ask1:.2f}')
print(f'  成交量:   {volume/10000:.1f} 万股')
print(f'  成交额:   {amount/100000000:.2f} 亿港币')
print(f'  均价:     {avg_price:.2f} 港币')

print('\n【技术分析】')
if price > pre_close:
    trend = '上涨  ↑'
elif price < pre_close:
    trend = '下跌  ↓'
else:
    trend = '平盘  →'
print(f'  今日趋势: {trend}')
print(f'  日内位置: {day_position:.1f}% (0%=今日最低, 100%=今日最高)')

if price > avg_price:
    print(f'  量价关系: 现价 > 均价，尾盘买盘占优')
else:
    print(f'  量价关系: 现价 < 均价，尾盘卖盘占优')

# 乖离分析
if bid1 > 0 and ask1 > 0:
    spread = (ask1 - bid1) / bid1 * 100
    print(f'  买卖价差: {spread:.3f}%  (越小流动性越好)')

if pe_ratio > 0:
    print(f'  市盈率:   {pe_ratio:.2f}x')

print('\n【52周价格区间】')
print(f'  52周最高: {week52_high:.2f} 港币')
print(f'  52周最低: {week52_low:.2f} 港币')
print(f'  当前位置: {week52_pos:.1f}% (52周区间内)')
dist_from_high = (week52_high - price) / price * 100
print(f'  距高点:   -{dist_from_high:.1f}%')

print('\n【关键价位】')
print(f'  今日支撑: {low:.2f} 港币')
print(f'  今日阻力: {high:.2f} 港币')
print(f'  +3% 压力: {price * 1.03:.2f} 港币')
print(f'  -3% 支撑: {price * 0.97:.2f} 港币')

print('\n【综合评估】')
signals = []
if change_pct > 3:
    signals.append('今日强势上涨，动能较强')
elif change_pct > 0:
    signals.append('今日小幅上涨')
elif change_pct < -3:
    signals.append('今日明显下跌，注意风险')
else:
    signals.append('今日小幅下跌')

if day_position > 80:
    signals.append('价格接近今日高点，短期有压力')
elif day_position < 20:
    signals.append('价格接近今日低点，可关注反弹')

if week52_pos > 80:
    signals.append('处于52周高位区间，估值偏高')
elif week52_pos < 20:
    signals.append('处于52周低位区间，有估值优势')

for s in signals:
    print(f'  • {s}')

print('=' * 60)
