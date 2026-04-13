#!/usr/bin/env python3
"""卓易信息(688258) 全面分析"""
import sys
import io
import urllib.request
import json
import re
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
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
        'User-Agent': 'Mozilla/5.0'
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
        'ask1': float(fields[20]) if fields[20] else 0,
        'date': fields[30],
        'time': fields[31],
    }

def get_daily_data(code, days=60):
    """获取日K数据"""
    if code.startswith('6') or code.startswith('688'):
        symbol = 'sh' + code
    else:
        symbol = 'sz' + code
    
    url = f"https://quotes.sina.cn/cn/api/jsonp_v2.php/var%20_{symbol}=/CN_MarketDataService.getKLineData?symbol={symbol}&scale=240&ma=no&datalen={days}"
    req = urllib.request.Request(url, headers={
        'Referer': 'http://finance.sina.com.cn',
        'User-Agent': 'Mozilla/5.0'
    })
    resp = urllib.request.urlopen(req, timeout=10)
    text = resp.read().decode('utf-8')
    
    match = re.search(r'\(\[(.*)\]\)', text, re.DOTALL)
    if not match:
        return None
    
    data = json.loads('[' + match.group(1) + ']')
    df = pd.DataFrame([{
        'date': d['day'],
        'open': float(d['open']),
        'high': float(d['high']),
        'low': float(d['low']),
        'close': float(d['close']),
        'volume': float(d['volume'])
    } for d in data])
    df['date'] = pd.to_datetime(df['date'])
    return df.sort_values('date').reset_index(drop=True)

def calculate_ma(df, periods=[5, 10, 20, 30, 60]):
    """计算移动平均线"""
    for p in periods:
        df[f'ma{p}'] = df['close'].rolling(window=p).mean()
    return df

def calculate_rsi(df, period=14):
    """计算RSI"""
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    return df

def calculate_macd(df):
    """计算MACD"""
    exp1 = df['close'].ewm(span=12, adjust=False).mean()
    exp2 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd'] = exp1 - exp2
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']
    return df

def calculate_bollinger(df, period=20, std=2):
    """计算布林带"""
    df['bb_middle'] = df['close'].rolling(window=period).mean()
    bb_std = df['close'].rolling(window=period).std()
    df['bb_upper'] = df['bb_middle'] + (bb_std * std)
    df['bb_lower'] = df['bb_middle'] - (bb_std * std)
    return df

# ========== 主程序 ==========
code = '688258'
print('=' * 70)
print(f'卓易信息({code}) - 全面分析报告')
print('=' * 70)

# 1. 实时行情
print('\n【一、实时行情】')
quote = get_realtime_quote(code)
if not quote:
    print('获取行情失败')
    sys.exit(1)

change_amt = quote['price'] - quote['pre_close']
change_pct = change_amt / quote['pre_close'] * 100 if quote['pre_close'] else 0
amplitude = (quote['high'] - quote['low']) / quote['pre_close'] * 100 if quote['pre_close'] else 0
avg_price = quote['amount'] / quote['volume'] if quote['volume'] else quote['price']

sign = '+' if change_amt >= 0 else ''
print(f"  股票名称: {quote['name']}")
print(f"  当前价格: {quote['price']:.2f} 元")
print(f"  今日涨跌: {sign}{change_pct:.2f}% ({sign}{change_amt:.2f}元)")
print(f"  今日开盘: {quote['open']:.2f} 元  昨收: {quote['pre_close']:.2f} 元")
print(f"  今日最高: {quote['high']:.2f} 元  最低: {quote['low']:.2f} 元")
print(f"  今日振幅: {amplitude:.2f}%")
print(f"  成交量:   {quote['volume']/10000:.2f} 万股")
print(f"  成交额:   {quote['amount']/100000000:.2f} 亿元")
print(f"  买卖盘:   买一 {quote['bid1']:.2f} / 卖一 {quote['ask1']:.2f}")
print(f"  更新时间: {quote['date']} {quote['time']}")

# 2. 历史数据分析
print('\n【二、近期走势分析】')
df = get_daily_data(code, 60)
if df is not None and len(df) > 20:
    df = calculate_ma(df)
    df = calculate_rsi(df)
    df = calculate_macd(df)
    df = calculate_bollinger(df)
    
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    
    print(f"\n  近60日统计:")
    print(f"    最高价: {df['high'].max():.2f} 元")
    print(f"    最低价: {df['low'].min():.2f} 元")
    print(f"    平均价: {df['close'].mean():.2f} 元")
    print(f"    波动率: {df['close'].std()/df['close'].mean()*100:.2f}%")
    
    # 近5日走势
    print(f"\n  近5日收盘价:")
    for i in range(-5, 0):
        row = df.iloc[i]
        change = (row['close'] - df.iloc[i-1]['close']) / df.iloc[i-1]['close'] * 100 if i > -len(df) else 0
        sign = '+' if change >= 0 else ''
        print(f"    {row['date'].strftime('%m-%d')}: {row['close']:.2f} ({sign}{change:.2f}%)")
    
    # 3. 技术指标分析
    print('\n【三、技术指标分析】')
    
    # 均线系统
    print(f"\n  均线系统:")
    ma_periods = [5, 10, 20, 30, 60]
    for p in ma_periods:
        if f'ma{p}' in latest and not pd.isna(latest[f'ma{p}']):
            status = "上方" if latest['close'] > latest[f'ma{p}'] else "下方"
            print(f"    MA{p}: {latest[f'ma{p}']:.2f}  ({status})")
    
    # 均线排列
    ma5, ma10, ma20 = latest.get('ma5', 0), latest.get('ma10', 0), latest.get('ma20', 0)
    if ma5 > ma10 > ma20:
        ma_trend = "多头排列 ↑ (短期>中期>长期)"
    elif ma5 < ma10 < ma20:
        ma_trend = "空头排列 ↓ (短期<中期<长期)"
    else:
        ma_trend = "震荡整理 → (均线纠缠)"
    print(f"    趋势判断: {ma_trend}")
    
    # RSI
    rsi = latest.get('rsi', 0)
    if not pd.isna(rsi):
        print(f"\n  RSI指标 (14日): {rsi:.2f}")
        if rsi > 70:
            rsi_status = "超买区域，注意回调风险"
        elif rsi > 50:
            rsi_status = "强势区域"
        elif rsi > 30:
            rsi_status = "弱势区域"
        else:
            rsi_status = "超卖区域，关注反弹机会"
        print(f"    状态: {rsi_status}")
    
    # MACD
    macd = latest.get('macd', 0)
    macd_signal = latest.get('macd_signal', 0)
    macd_hist = latest.get('macd_hist', 0)
    if not pd.isna(macd):
        print(f"\n  MACD指标:")
        print(f"    DIF:  {macd:.4f}")
        print(f"    DEA:  {macd_signal:.4f}")
        print(f"    MACD: {macd_hist:.4f}")
        
        if macd > macd_signal:
            macd_trend = "金叉状态 (DIF>DEA)，偏多"
        else:
            macd_trend = "死叉状态 (DIF<DEA)，偏空"
        
        if macd_hist > prev.get('macd_hist', 0):
            macd_momentum = "红柱放大，动能增强"
        else:
            macd_momentum = "红柱缩小，动能减弱"
        
        print(f"    信号: {macd_trend}")
        print(f"    动能: {macd_momentum}")
    
    # 布林带
    bb_upper = latest.get('bb_upper', 0)
    bb_middle = latest.get('bb_middle', 0)
    bb_lower = latest.get('bb_lower', 0)
    if not pd.isna(bb_upper):
        print(f"\n  布林带 (20日):")
        print(f"    上轨: {bb_upper:.2f}")
        print(f"    中轨: {bb_middle:.2f}")
        print(f"    下轨: {bb_lower:.2f}")
        
        close = latest['close']
        if close > bb_upper:
            bb_status = "突破上轨，超买"
        elif close < bb_lower:
            bb_status = "跌破下轨，超卖"
        elif close > bb_middle:
            bb_status = "中轨上方，偏多"
        else:
            bb_status = "中轨下方，偏空"
        print(f"    状态: {bb_status}")
    
    # 4. 综合评分
    print('\n【四、综合评分】')
    score = 50  # 基础分
    reasons = []
    
    # 趋势评分
    if latest.get('ma5', 0) > latest.get('ma10', 0):
        score += 10
        reasons.append("MA5>MA10 (+10)")
    else:
        score -= 10
        reasons.append("MA5<MA10 (-10)")
    
    if latest.get('ma10', 0) > latest.get('ma20', 0):
        score += 10
        reasons.append("MA10>MA20 (+10)")
    else:
        score -= 10
        reasons.append("MA10<MA20 (-10)")
    
    # RSI评分
    rsi = latest.get('rsi', 50)
    if 40 < rsi < 60:
        score += 5
        reasons.append(f"RSI适中 ({rsi:.1f}) (+5)")
    elif rsi > 70:
        score -= 15
        reasons.append(f"RSI超买 ({rsi:.1f}) (-15)")
    elif rsi < 30:
        score += 15
        reasons.append(f"RSI超卖 ({rsi:.1f}) (+15)")
    
    # MACD评分
    if latest.get('macd', 0) > latest.get('macd_signal', 0):
        score += 10
        reasons.append("MACD金叉 (+10)")
    else:
        score -= 10
        reasons.append("MACD死叉 (-10)")
    
    # 布林带评分
    close = latest['close']
    if close > latest.get('bb_middle', close):
        score += 5
        reasons.append("价格>布林带中轨 (+5)")
    else:
        score -= 5
        reasons.append("价格<布林带中轨 (-5)")
    
    # 今日涨跌
    if change_pct > 5:
        score += 5
        reasons.append(f"今日大涨 {change_pct:.1f}% (+5)")
    elif change_pct < -5:
        score -= 5
        reasons.append(f"今日大跌 {change_pct:.1f}% (-5)")
    
    score = max(0, min(100, score))  # 限制在0-100
    
    print(f"  综合评分: {score}/100")
    if score >= 80:
        rating = "★★★★★ 强烈看多"
    elif score >= 60:
        rating = "★★★★☆ 偏多"
    elif score >= 40:
        rating = "★★★☆☆ 中性"
    elif score >= 20:
        rating = "★★☆☆☆ 偏空"
    else:
        rating = "★☆☆☆☆ 强烈看空"
    print(f"  评级: {rating}")
    
    print(f"\n  评分明细:")
    for r in reasons:
        print(f"    • {r}")
    
    # 5. 操作建议
    print('\n【五、操作建议】')
    print('-' * 70)
    
    suggestions = []
    
    if score >= 70:
        suggestions.append("技术面偏多，可考虑逢低介入")
    elif score <= 30:
        suggestions.append("技术面偏空，建议观望或减仓")
    else:
        suggestions.append("技术面中性，建议观望等待方向")
    
    if rsi < 30:
        suggestions.append("RSI超卖，短期或有反弹")
    elif rsi > 70:
        suggestions.append("RSI超买，注意回调风险")
    
    if latest.get('macd', 0) > latest.get('macd_signal', 0) and prev.get('macd', 0) <= prev.get('macd_signal', 0):
        suggestions.append("MACD刚形成金叉，关注上涨持续性")
    elif latest.get('macd', 0) < latest.get('macd_signal', 0) and prev.get('macd', 0) >= prev.get('macd_signal', 0):
        suggestions.append("MACD刚形成死叉，注意下跌风险")
    
    for s in suggestions:
        print(f"  • {s}")
    
    # 6. 关键价位
    print('\n【六、关键价位】')
    print(f"  强支撑: {df['low'].min():.2f} 元 (60日最低)")
    print(f"  支撑1:  {latest.get('bb_lower', df['low'].min()):.2f} 元 (布林带下轨)")
    print(f"  支撑2:  {latest.get('ma20', df['close'].mean()):.2f} 元 (MA20)")
    print(f"  当前价: {latest['close']:.2f} 元")
    print(f"  压力1:  {latest.get('ma5', latest['close']*1.02):.2f} 元 (MA5)")
    print(f"  压力2:  {latest.get('bb_upper', latest['close']*1.05):.2f} 元 (布林带上轨)")
    print(f"  强阻力: {df['high'].max():.2f} 元 (60日最高)")

print('\n' + '=' * 70)
print('分析完成')
print('=' * 70)
