#!/usr/bin/env python3
"""卓易信息(688258) 今日行情深度分析"""
import sys
import io
import urllib.request
import json
import re
from datetime import datetime
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def get_realtime_quote(code):
    """获取实时行情"""
    if code.startswith('6') or code.startswith('688'):
        symbol = 'sh' + code
    else:
        symbol = 'sz' + code
    
    url = f'http://hq.sinajs.cn/list={symbol}'
    req = urllib.request.Request(url, headers={
        'Referer': 'http://finance.sina.com.cn',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })
    resp = urllib.request.urlopen(req, timeout=10)
    text = resp.read().decode('gbk')
    
    match = re.search(r'="(.*)"', text)
    if not match:
        return None
    
    fields = match.group(1).split(',')
    if len(fields) < 32:
        return None
    
    return {
        'name': fields[0],
        'open': float(fields[1]) if fields[1] else 0,
        'pre_close': float(fields[2]) if fields[2] else 0,
        'price': float(fields[3]) if fields[3] else 0,
        'high': float(fields[4]) if fields[4] else 0,
        'low': float(fields[5]) if fields[5] else 0,
        'volume': int(float(fields[8])) if fields[8] else 0,
        'amount': float(fields[9]) if fields[9] else 0,
        'bid1': float(fields[10]) if fields[10] else 0,
        'bid1_vol': int(float(fields[11])) if fields[11] else 0,
        'bid2': float(fields[12]) if fields[12] else 0,
        'bid2_vol': int(float(fields[13])) if fields[13] else 0,
        'bid3': float(fields[14]) if fields[14] else 0,
        'bid3_vol': int(float(fields[15])) if fields[15] else 0,
        'bid4': float(fields[16]) if fields[16] else 0,
        'bid4_vol': int(float(fields[17])) if fields[17] else 0,
        'bid5': float(fields[18]) if fields[18] else 0,
        'bid5_vol': int(float(fields[19])) if fields[19] else 0,
        'ask1': float(fields[20]) if fields[20] else 0,
        'ask1_vol': int(float(fields[21])) if fields[21] else 0,
        'ask2': float(fields[22]) if fields[22] else 0,
        'ask2_vol': int(float(fields[23])) if fields[23] else 0,
        'ask3': float(fields[24]) if fields[24] else 0,
        'ask3_vol': int(float(fields[25])) if fields[25] else 0,
        'ask4': float(fields[26]) if fields[26] else 0,
        'ask4_vol': int(float(fields[27])) if fields[27] else 0,
        'ask5': float(fields[28]) if fields[28] else 0,
        'ask5_vol': int(float(fields[29])) if fields[29] else 0,
        'date': fields[30],
        'time': fields[31],
    }

def get_minute_data(code):
    """获取分时数据"""
    if code.startswith('6') or code.startswith('688'):
        symbol = 'sh' + code
    else:
        symbol = 'sz' + code
    
    import urllib.parse
    url = f"https://quotes.sina.cn/cn/api/jsonp_v2.php/var%20_/CN_MarketDataService.getKLineData?symbol={symbol}&scale=1&ma=no&datalen=250"
    req = urllib.request.Request(url, headers={
        'Referer': 'http://finance.sina.com.cn',
        'User-Agent': 'Mozilla/5.0'
    })
    resp = urllib.request.urlopen(req, timeout=10)
    text = resp.read().decode('utf-8')
    
    match = re.search(r'\(\[(.*)\]\)', text, re.DOTALL)
    if not match:
        return []
    
    data = json.loads('[' + match.group(1) + ']')
    return [{
        'time': d['day'],
        'open': float(d['open']),
        'high': float(d['high']),
        'low': float(d['low']),
        'close': float(d['close']),
        'volume': int(d['volume']),
        'amount': float(d['amount'])
    } for d in data]

def analyze_minute_volume(minute_data):
    """分析分时量能"""
    if not minute_data:
        return None
    
    # 过滤今日交易数据
    today = minute_data[-1]['time'][:10] if minute_data else ''
    today_data = [d for d in minute_data if d['time'].startswith(today) and d['volume'] > 0]
    
    if not today_data:
        return None
    
    total_vol = sum(d['volume'] for d in today_data)
    total_amt = sum(d['amount'] for d in today_data)
    
    # 按时段统计
    def period_vol(data, start_h, start_m, end_h, end_m):
        vol = 0
        for d in data:
            t = d['time'][-8:]
            h, m = int(t[:2]), int(t[3:5])
            if (h > start_h or (h == start_h and m >= start_m)) and (h < end_h or (h == end_h and m < end_m)):
                vol += d['volume']
        return vol
    
    open_30 = period_vol(today_data, 9, 30, 10, 0)
    mid_am = period_vol(today_data, 10, 0, 11, 30)
    mid_pm = period_vol(today_data, 13, 0, 14, 30)
    close_30 = period_vol(today_data, 14, 30, 15, 1)
    
    # 放量TOP5
    sorted_data = sorted(today_data, key=lambda x: x['volume'], reverse=True)[:5]
    
    return {
        'total_vol': total_vol,
        'total_amt': total_amt,
        'open_30': open_30,
        'open_30_pct': open_30 / total_vol * 100 if total_vol else 0,
        'mid_am': mid_am,
        'mid_am_pct': mid_am / total_vol * 100 if total_vol else 0,
        'mid_pm': mid_pm,
        'mid_pm_pct': mid_pm / total_vol * 100 if total_vol else 0,
        'close_30': close_30,
        'close_30_pct': close_30 / total_vol * 100 if total_vol else 0,
        'top5': sorted_data,
        'today_date': today
    }

# ========== 主程序 ==========
code = '688258'
print('=' * 65)
print(f"卓易信息({code}) - 今日行情深度分析")
print('=' * 65)

# 1. 实时行情
print('\n【一、实时行情】')
quote = get_realtime_quote(code)
if not quote:
    print('获取行情失败')
    sys.exit(1)

change_amt = quote['price'] - quote['pre_close']
change_pct = change_amt / quote['pre_close'] * 100 if quote['pre_close'] else 0
amplitude = (quote['high'] - quote['low']) / quote['pre_close'] * 100 if quote['pre_close'] else 0
day_pos = (quote['price'] - quote['low']) / (quote['high'] - quote['low']) * 100 if quote['high'] != quote['low'] else 50
avg_price = quote['amount'] / quote['volume'] if quote['volume'] else quote['price']

sign = '+' if change_amt >= 0 else ''
print(f"  股票名称: {quote['name']}")
print(f"  当前价格: {quote['price']:.2f} 元    涨跌: {sign}{change_pct:.2f}% ({sign}{change_amt:.2f}元)")
print(f"  今日开盘: {quote['open']:.2f} 元    昨收: {quote['pre_close']:.2f} 元")
print(f"  今日最高: {quote['high']:.2f} 元    最低: {quote['low']:.2f} 元")
print(f"  今日振幅: {amplitude:.2f}%")
print(f"  成交量:   {quote['volume']/10000:.2f} 万股")
print(f"  成交额:   {quote['amount']/100000000:.2f} 亿元")
print(f"  日内均价: {avg_price:.2f} 元")
print(f"  更新时间: {quote['date']} {quote['time']}")

# 2. 买卖盘口
print('\n【二、五档盘口】')
print(f"  档位    买入量(手)   价格    卖出量(手)   价格")
print(f"  ─────────────────────────────────────────")
print(f"   五档    {quote['bid5_vol']:>8}    {quote['bid5']:>7.2f}    {quote['ask5_vol']:>8}    {quote['ask5']:>7.2f}")
print(f"   四档    {quote['bid4_vol']:>8}    {quote['bid4']:>7.2f}    {quote['ask4_vol']:>8}    {quote['ask4']:>7.2f}")
print(f"   三档    {quote['bid3_vol']:>8}    {quote['bid3']:>7.2f}    {quote['ask3_vol']:>8}    {quote['ask3']:>7.2f}")
print(f"   二档    {quote['bid2_vol']:>8}    {quote['bid2']:>7.2f}    {quote['ask2_vol']:>8}    {quote['ask2']:>7.2f}")
print(f"   一档    {quote['bid1_vol']:>8}    {quote['bid1']:>7.2f}    {quote['ask1_vol']:>8}    {quote['ask1']:>7.2f}")

bid_total = quote['bid1_vol'] + quote['bid2_vol'] + quote['bid3_vol'] + quote['bid4_vol'] + quote['bid5_vol']
ask_total = quote['ask1_vol'] + quote['ask2_vol'] + quote['ask3_vol'] + quote['ask4_vol'] + quote['ask5_vol']
print(f"  ─────────────────────────────────────────")
print(f"   合计    {bid_total:>8}              {ask_total:>8}")
if bid_total > ask_total * 1.5:
    print(f"  盘口分析: 买盘明显占优，买/卖 = {bid_total/ask_total:.2f}")
elif ask_total > bid_total * 1.5:
    print(f"  盘口分析: 卖盘明显占优，买/卖 = {bid_total/ask_total:.2f}")
else:
    print(f"  盘口分析: 盘口相对均衡，买/卖 = {bid_total/ask_total:.2f}")

# 3. 分时量能分析
print('\n【三、分时量能分析】')
minute_data = get_minute_data(code)
vol_analysis = analyze_minute_volume(minute_data)

if vol_analysis:
    print(f"  分析日期: {vol_analysis['today_date']}")
    print(f"  全天成交: {vol_analysis['total_vol']/10000:.2f} 万股  ({vol_analysis['total_amt']/100000000:.2f} 亿元)")
    print(f"\n  时段分布:")
    print(f"    早盘30分 (09:30-10:00): {vol_analysis['open_30']/10000:>8.2f}万股  ({vol_analysis['open_30_pct']:.1f}%)")
    print(f"    上午中段 (10:00-11:30): {vol_analysis['mid_am']/10000:>8.2f}万股  ({vol_analysis['mid_am_pct']:.1f}%)")
    print(f"    下午中段 (13:00-14:30): {vol_analysis['mid_pm']/10000:>8.2f}万股  ({vol_analysis['mid_pm_pct']:.1f}%)")
    print(f"    尾盘30分 (14:30-15:00): {vol_analysis['close_30']/10000:>8.2f}万股  ({vol_analysis['close_30_pct']:.1f}%)")
    
    print(f"\n  放量时段 TOP 5:")
    for i, d in enumerate(vol_analysis['top5'], 1):
        print(f"    {i}. {d['time'][-8:]}  价格:{d['close']:.2f}  成交:{d['volume']/10000:.2f}万股")
    
    # 主力动向判断
    signals = []
    if vol_analysis['open_30_pct'] > 35:
        signals.append("早盘大幅放量，主力资金积极进场")
    elif vol_analysis['open_30_pct'] > 25:
        signals.append("早盘放量明显")
    
    if vol_analysis['close_30_pct'] > 25:
        signals.append("尾盘大幅放量，关注资金动向")
    elif vol_analysis['close_30_pct'] > 15:
        signals.append("尾盘有一定放量")
    
    if signals:
        print(f"\n  主力动向:")
        for s in signals:
            print(f"    • {s}")

# 4. 技术指标分析
print('\n【四、技术分析】')
if change_pct > 9:
    trend = "★★★ 涨停或接近涨停"
elif change_pct > 5:
    trend = "★★☆ 强势上涨"
elif change_pct > 2:
    trend = "★☆☆ 温和上涨"
elif change_pct > 0:
    trend = "☆☆☆ 小幅上涨"
elif change_pct > -2:
    trend = "☆☆★ 小幅下跌"
elif change_pct > -5:
    trend = "☆★★ 明显下跌"
else:
    trend = "★★★ 大幅下跌"
print(f"  日内趋势: {trend}")
print(f"  日内位置: {day_pos:.1f}%  (0%=最低, 100%=最高)")

if quote['price'] > avg_price:
    print(f"  均价分析: 现价 > 均价，尾盘买盘强")
elif quote['price'] < avg_price:
    print(f"  均价分析: 现价 < 均价，尾盘卖盘强")
else:
    print(f"  均价分析: 现价 = 均价，多空平衡")

# K线形态
body = abs(quote['price'] - quote['open'])
upper_shadow = quote['high'] - max(quote['price'], quote['open'])
lower_shadow = min(quote['price'], quote['open']) - quote['low']
total_range = quote['high'] - quote['low']

if total_range > 0:
    body_pct = body / total_range * 100
    upper_pct = upper_shadow / total_range * 100
    lower_pct = lower_shadow / total_range * 100
    print(f"\n  K线形态:")
    print(f"    实体占比: {body_pct:.1f}%")
    print(f"    上影线:   {upper_pct:.1f}%")
    print(f"    下影线:   {lower_pct:.1f}%")
    
    if quote['price'] > quote['open']:  # 阳线
        if lower_pct > 30 and upper_pct < 10:
            print(f"    形态判断: 长下影阳线，底部支撑强")
        elif body_pct > 70:
            print(f"    形态判断: 大阳线，多方强势")
        elif upper_pct > 30:
            print(f"    形态判断: 上影阳线，上方有压力")
    else:  # 阴线
        if upper_pct > 30 and lower_pct < 10:
            print(f"    形态判断: 长上影阴线，上方压力重")
        elif body_pct > 70:
            print(f"    形态判断: 大阴线，空方强势")

# 5. 综合评估
print('\n【五、综合评估】')
print('-' * 65)

evaluations = []

# 涨跌评估
if change_pct > 9:
    evaluations.append("今日涨停或接近涨停，表现极为强势")
elif change_pct > 5:
    evaluations.append("今日大涨，表现强势")
elif change_pct < -5:
    evaluations.append("今日大跌，注意风险")

# 量能评估
if vol_analysis:
    if vol_analysis['open_30_pct'] > 35:
        evaluations.append("早盘放量明显，资金积极介入")
    if vol_analysis['close_30_pct'] > 20:
        evaluations.append("尾盘放量，关注主力动向")

# 盘口评估
if bid_total > ask_total * 2:
    evaluations.append("买盘远大于卖盘，看多情绪浓")
elif ask_total > bid_total * 2:
    evaluations.append("卖盘远大于买盘，抛压较重")

# 位置评估
if day_pos > 80:
    evaluations.append("价格接近日内高点，短期有压力")
elif day_pos < 20:
    evaluations.append("价格接近日内低点，关注反弹机会")

for e in evaluations:
    print(f"  • {e}")

print('\n【六、关键价位】')
print(f"  强支撑:   {quote['low']:.2f} 元 (今日最低)")
print(f"  弱支撑:   {quote['pre_close']:.2f} 元 (昨日收盘)")
print(f"  当前价:   {quote['price']:.2f} 元")
print(f"  弱阻力:   {quote['high']:.2f} 元 (今日最高)")
print(f"  强阻力:   {quote['high'] * 1.02:.2f} 元 (+2%)")

print('\n' + '=' * 65)
