#!/usr/bin/env python3
"""近一个月实盘分析"""
import urllib.request
import re
import json
from datetime import datetime, timedelta

def get_realtime(code):
    """获取实时行情"""
    if code.startswith('6'):
        symbol = 'sh' + code
    else:
        symbol = 'sz' + code

    url = f"https://hq.sinajs.cn/list={symbol}"
    req = urllib.request.Request(url, headers={
        "Referer": "https://finance.sina.com.cn",
        "User-Agent": "Mozilla/5.0",
    })
    resp = urllib.request.urlopen(req, timeout=10)
    text = resp.read().decode("gbk")

    match = re.search(r'var hq_str_\w+="([^"]*)"', text)
    if match:
        fields = match.group(1).split(',')
        return {
            'name': fields[0],
            'open': float(fields[1]) if fields[1] else 0,
            'pre_close': float(fields[2]) if fields[2] else 0,
            'price': float(fields[3]) if fields[3] else 0,
            'high': float(fields[4]) if fields[4] else 0,
            'low': float(fields[5]) if fields[5] else 0,
            'volume': float(fields[8]) if fields[8] else 0,
            'amount': float(fields[9]) if fields[9] else 0,
        }
    return None

def get_minute_data(code):
    """获取分时数据"""
    market = 1 if code.startswith('6') else 0
    url = f"http://push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {
        'fields1': 'f1,f2,f3,f4,f5,f6',
        'fields2': 'f51,f52,f53,f54,f55,f56,f57',
        'ut': '7eea3edcaed734bea9cbfc24409ed989',
        'klt': '101',  # 日K
        'fqt': '1',
        'secid': f'{market}.{code}',
        'lmt': '30'  # 最近30条
    }

    try:
        url_with_params = url + '?' + '&'.join([f'{k}={v}' for k, v in params.items()])
        req = urllib.request.Request(url_with_params, headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://quote.eastmoney.com/",
        })
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read().decode())

        if data.get('data') and data['data'].get('klines'):
            rows = []
            for line in data['data']['klines']:
                parts = line.split(',')
                rows.append({
                    'date': parts[0],
                    'open': float(parts[1]),
                    'close': float(parts[2]),
                    'high': float(parts[3]),
                    'low': float(parts[4]),
                    'volume': float(parts[5]),
                })
            return rows
    except Exception as e:
        print(f"获取历史数据失败: {e}")
    return []

# 主程序
print("=" * 60)
print("卓易信息 (688258) 近一个月实盘分析")
print("=" * 60)

# 获取实时行情
rt = get_realtime('688258')
if rt:
    change_pct = (rt['price'] - rt['pre_close']) / rt['pre_close'] * 100 if rt['pre_close'] else 0
    print(f"\n【今日实时行情】")
    print(f"  现价: {rt['price']:.2f}  涨跌: {change_pct:+.2f}%")
    print(f"  今开: {rt['open']:.2f}  最高: {rt['high']:.2f}  最低: {rt['low']:.2f}")
    print(f"  昨收: {rt['pre_close']:.2f}")
    print(f"  成交量: {rt['volume']/10000:.2f}万手  成交额: {rt['amount']/100000000:.2f}亿")

# 获取历史数据
print(f"\n【获取近一个月历史数据...】")
hist = get_minute_data('688258')

if hist:
    print(f"获取到 {len(hist)} 条日K数据")
    print(f"\n{'日期':<12} {'开盘':>8} {'收盘':>8} {'最高':>8} {'最低':>8} {'涨跌%':>8}")
    print("-" * 60)

    total_return = 0
    for i, row in enumerate(hist):
        chg = (row['close'] - row['open']) / row['open'] * 100 if row['open'] else 0
        print(f"{row['date']:<12} {row['open']:>8.2f} {row['close']:>8.2f} {row['high']:>8.2f} {row['low']:>8.2f} {chg:>+7.2f}%")

    # 计算统计
    closes = [r['close'] for r in hist]
    if len(closes) > 1:
        month_return = (closes[-1] - closes[0]) / closes[0] * 100
        max_price = max(r['high'] for r in hist)
        min_price = min(r['low'] for r in hist)

        print(f"\n【近一个月统计】")
        print(f"  期初价格: {closes[0]:.2f} 元")
        print(f"  期末价格: {closes[-1]:.2f} 元")
        print(f"  最高价格: {max_price:.2f} 元")
        print(f"  最低价格: {min_price:.2f} 元")
        print(f"  区间涨幅: {month_return:+.2f}%")
        print(f"  区间振幅: {(max_price - min_price) / min_price * 100:.2f}%")

        # 均线分析
        if len(closes) >= 5:
            ma5 = sum(closes[-5:]) / 5
            print(f"\n【技术指标】")
            print(f"  MA5: {ma5:.2f} 元")
            if len(closes) >= 20:
                ma20 = sum(closes[-20:]) / 20
                print(f"  MA20: {ma20:.2f} 元")
                if closes[-1] > ma5 > ma20:
                    print(f"  状态: 多头排列，趋势向上")
                elif closes[-1] < ma5 < ma20:
                    print(f"  状态: 空头排列，趋势向下")
                else:
                    print(f"  状态: 均线纠缠，方向不明")
else:
    print("无法获取历史数据")

print("\n" + "=" * 60)
