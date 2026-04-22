"""
个股技术分析脚本
功能:
  - 均线分析 (MA5/MA10/MA20/MA60)
  - 量价分析 (量比、成交额趋势、价量配合)
  - MACD 指标 (DIF/DEA/MACD柱)
  - 综合评分 (0~100分)
  - 支持多只股票批量分析

用法:
  python analyze.py                           # 使用配置文件中的watchlist
  python analyze.py --codes 688268 688661     # 指定股票代码
  python analyze.py --codes 688268 --days 60  # 分析最近60个交易日
  python analyze.py --codes 688268 --save     # 保存分析结果到CSV
"""

import sys
import os
import io
import time
import argparse
import pandas as pd

# 修复 Windows 终端中文输出乱码
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
import numpy as np
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Tuple
import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from data.realtime import RealtimeFetcher, RealtimeQuote
from data.fetcher import DataFetcher


# ========== 配置加载 ==========

def load_config() -> dict:
    config_path = os.path.join(os.path.dirname(__file__), 'config', 'settings.yaml')
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception:
        return {}


# ========== 技术指标计算 ==========

def calc_ma(closes: np.ndarray, period: int) -> np.ndarray:
    """计算简单移动平均线"""
    ma = np.full_like(closes, np.nan)
    for i in range(period - 1, len(closes)):
        ma[i] = np.mean(closes[i - period + 1:i + 1])
    return ma


def calc_ema(closes: np.ndarray, period: int) -> np.ndarray:
    """计算指数移动平均线"""
    ema = np.full_like(closes, np.nan, dtype=float)
    k = 2.0 / (period + 1)
    # 找第一个非nan起始点
    start = 0
    while start < len(closes) and np.isnan(closes[start]):
        start += 1
    if start >= len(closes):
        return ema
    ema[start] = closes[start]
    for i in range(start + 1, len(closes)):
        ema[i] = closes[i] * k + ema[i - 1] * (1 - k)
    return ema


def calc_macd(closes: np.ndarray, fast=12, slow=26, signal=9) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """计算 MACD 指标
    返回: (DIF, DEA, MACD柱)
    """
    ema_fast = calc_ema(closes, fast)
    ema_slow = calc_ema(closes, slow)
    dif = ema_fast - ema_slow
    dea = calc_ema(dif, signal)
    macd_bar = (dif - dea) * 2
    return dif, dea, macd_bar


def calc_volume_ratio(volumes: np.ndarray, today_vol: float, days: int = 5) -> float:
    """计算量比 = 今日成交量 / 过去N日平均成交量"""
    if len(volumes) < days + 1:
        return 1.0
    avg = np.mean(volumes[-(days + 1):-1])
    if avg == 0:
        return 1.0
    return today_vol / avg


def calc_rsi(closes: np.ndarray, period: int = 14) -> np.ndarray:
    """计算RSI"""
    rsi = np.full_like(closes, np.nan)
    if len(closes) < period + 1:
        return rsi
    deltas = np.diff(closes)
    for i in range(period, len(closes)):
        gains = deltas[i - period:i]
        avg_gain = np.mean(gains[gains > 0]) if np.any(gains > 0) else 0
        avg_loss = np.mean(-gains[gains < 0]) if np.any(gains < 0) else 0
        if avg_loss == 0:
            rsi[i] = 100
        else:
            rs = avg_gain / avg_loss
            rsi[i] = 100 - 100 / (1 + rs)
    return rsi


def analyze_stock(code: str, fetcher_hist: DataFetcher, fetcher_rt: RealtimeFetcher,
                  analysis_days: int = 60) -> Optional[dict]:
    """对单只股票进行完整技术分析"""

    # 1. 获取历史数据
    try:
        df = fetcher_hist.get_a_share_daily(code, start_date='2025-01-01')
    except Exception as e:
        print(f"  获取历史数据失败 {code}: {e}")
        return None

    if df is None or len(df) < 30:
        print(f"  {code}: 历史数据不足（{len(df) if df is not None else 0}条）")
        return None

    # 统一列名
    col_map = {}
    for col in df.columns:
        low = col.lower()
        if col in ['收盘', '收盘价'] or low == 'close':
            col_map['close'] = col
        elif col in ['开盘', '开盘价'] or low == 'open':
            col_map['open'] = col
        elif col in ['最高', '最高价'] or low == 'high':
            col_map['high'] = col
        elif col in ['最低', '最低价'] or low == 'low':
            col_map['low'] = col
        elif col in ['成交量'] or low in ['volume', 'vol']:
            col_map['volume'] = col
        elif col in ['成交额'] or low == 'amount':
            col_map['amount'] = col
        elif col in ['日期'] or low == 'date':
            col_map['date'] = col

    if 'close' not in col_map:
        print(f"  {code}: 找不到收盘价列，columns={list(df.columns)}")
        return None

    # 排序并截取最近 analysis_days 条
    if 'date' in col_map:
        df = df.sort_values(col_map['date']).reset_index(drop=True)
    df_recent = df.tail(analysis_days).reset_index(drop=True)

    closes = df_recent[col_map['close']].astype(float).values
    volumes = df_recent[col_map['volume']].astype(float).values if 'volume' in col_map else None
    amounts = df_recent[col_map['amount']].astype(float).values if 'amount' in col_map else None

    n = len(closes)

    # 2. 获取实时行情（补充今日数据）
    quote = fetcher_rt.get_quote(code)
    if quote:
        # 把今日数据追加到末尾
        today_close = quote.price
        today_vol = quote.volume
        today_amount = quote.amount
        closes = np.append(closes, today_close)
        if volumes is not None:
            volumes = np.append(volumes, today_vol)
        if amounts is not None:
            amounts = np.append(amounts, today_amount)
    else:
        today_close = closes[-1]
        today_vol = volumes[-1] if volumes is not None else 0
        today_amount = amounts[-1] if amounts is not None else 0

    n = len(closes)

    # 3. 均线
    ma5_arr = calc_ma(closes, 5)
    ma10_arr = calc_ma(closes, 10)
    ma20_arr = calc_ma(closes, 20)
    ma60_arr = calc_ma(closes, 60)

    ma5 = ma5_arr[-1] if not np.isnan(ma5_arr[-1]) else None
    ma10 = ma10_arr[-1] if not np.isnan(ma10_arr[-1]) else None
    ma20 = ma20_arr[-1] if not np.isnan(ma20_arr[-1]) else None
    ma60 = ma60_arr[-1] if not np.isnan(ma60_arr[-1]) else None

    # 均线趋势（近5日斜率）
    def ma_slope(arr):
        valid = arr[~np.isnan(arr)]
        if len(valid) < 5:
            return 0
        seg = valid[-5:]
        return (seg[-1] - seg[0]) / seg[0] * 100  # 近5日涨幅%

    ma5_slope = ma_slope(ma5_arr)
    ma10_slope = ma_slope(ma10_arr)
    ma20_slope = ma_slope(ma20_arr)

    # 4. MACD
    dif_arr, dea_arr, macd_arr = calc_macd(closes)
    dif = float(dif_arr[-1]) if not np.isnan(dif_arr[-1]) else None
    dea = float(dea_arr[-1]) if not np.isnan(dea_arr[-1]) else None
    macd_bar = float(macd_arr[-1]) if not np.isnan(macd_arr[-1]) else None
    # 金叉/死叉检测（最近两根）
    macd_cross = None
    if len(dif_arr) >= 2 and not np.isnan(dif_arr[-2]) and not np.isnan(dea_arr[-2]):
        prev_dif, prev_dea = dif_arr[-2], dea_arr[-2]
        curr_dif, curr_dea = dif_arr[-1], dea_arr[-1]
        if prev_dif < prev_dea and curr_dif >= curr_dea:
            macd_cross = "金叉"
        elif prev_dif > prev_dea and curr_dif <= curr_dea:
            macd_cross = "死叉"

    # 5. 量价分析
    vol_ratio = None
    if volumes is not None and len(volumes) >= 6:
        vol_ratio = calc_volume_ratio(volumes, volumes[-1])

    # 成交额近5日趋势（用最近5日平均与前5日平均比较，更稳健）
    amount_trend = None
    if amounts is not None and len(amounts) >= 10:
        amt_recent = np.mean(amounts[-5:])
        amt_prev = np.mean(amounts[-10:-5])
        if amt_prev > 1e4:  # 防止除以接近0的值
            amount_trend = (amt_recent - amt_prev) / amt_prev * 100

    # 连续放量天数
    consec_vol_up = 0
    if volumes is not None and len(volumes) >= 2:
        for i in range(len(volumes) - 1, 0, -1):
            if volumes[i] > volumes[i - 1]:
                consec_vol_up += 1
            else:
                break

    # 6. RSI
    rsi_arr = calc_rsi(closes, 14)
    rsi = float(rsi_arr[-1]) if not np.isnan(rsi_arr[-1]) else None

    # 7. 综合评分
    score, score_details = compute_score(
        price=today_close,
        ma5=ma5, ma10=ma10, ma20=ma20, ma60=ma60,
        ma5_slope=ma5_slope, ma10_slope=ma10_slope, ma20_slope=ma20_slope,
        dif=dif, dea=dea, macd_bar=macd_bar, macd_cross=macd_cross,
        vol_ratio=vol_ratio, amount_trend=amount_trend, consec_vol_up=consec_vol_up,
        rsi=rsi,
        change_pct=quote.change_pct if quote else 0,
    )

    return {
        'code': code,
        'name': quote.name if quote else code,
        'price': today_close,
        'change_pct': quote.change_pct if quote else 0,
        'amount': today_amount,
        # 均线
        'ma5': ma5, 'ma10': ma10, 'ma20': ma20, 'ma60': ma60,
        'ma5_slope': ma5_slope, 'ma10_slope': ma10_slope, 'ma20_slope': ma20_slope,
        # MACD
        'dif': dif, 'dea': dea, 'macd_bar': macd_bar, 'macd_cross': macd_cross,
        # 量价
        'vol_ratio': vol_ratio, 'amount_trend': amount_trend, 'consec_vol_up': consec_vol_up,
        # RSI
        'rsi': rsi,
        # 评分
        'score': score, 'score_details': score_details,
    }


def compute_score(
    price, ma5, ma10, ma20, ma60,
    ma5_slope, ma10_slope, ma20_slope,
    dif, dea, macd_bar, macd_cross,
    vol_ratio, amount_trend, consec_vol_up,
    rsi, change_pct,
) -> Tuple[float, Dict]:
    """综合评分 (0~100)"""
    details = {}
    total = 0.0

    # ---- 均线系统 (40分) ----
    ma_score = 0.0
    # 多头排列
    if ma5 and ma10 and ma20:
        if ma5 > ma10 > ma20:
            ma_score += 20
            details['均线排列'] = "多头排列(+20)"
        elif ma5 > ma10:
            ma_score += 10
            details['均线排列'] = "MA5>MA10(+10)"
        else:
            details['均线排列'] = "空头/混乱(+0)"
    # 价格站上MA5
    if ma5 and price > ma5:
        ma_score += 8
        details['价格位置'] = f"站上MA5(+8), 偏离{(price-ma5)/ma5*100:.1f}%"
    elif ma5:
        details['价格位置'] = f"低于MA5(+0)"
    # MA5斜率向上
    if ma5_slope > 0.5:
        ma_score += 7
        details['MA5趋势'] = f"向上(+7), 斜率{ma5_slope:.2f}%"
    elif ma5_slope > 0:
        ma_score += 3
        details['MA5趋势'] = f"微上(+3), 斜率{ma5_slope:.2f}%"
    else:
        details['MA5趋势'] = f"向下(+0), 斜率{ma5_slope:.2f}%"
    # MA60位置
    if ma60 and price > ma60:
        ma_score += 5
        details['MA60位置'] = f"站上MA60(+5)"
    elif ma60:
        details['MA60位置'] = f"低于MA60(+0)"
    total += min(ma_score, 40)
    details['均线评分'] = f"{min(ma_score, 40):.0f}/40"

    # ---- MACD (25分) ----
    macd_score = 0.0
    if dif is not None and dea is not None:
        if dif > 0 and dea > 0:
            macd_score += 10
            details['MACD区域'] = "零轴上方(+10)"
        elif dif > 0:
            macd_score += 5
            details['MACD区域'] = "DIF在零轴上(+5)"
        elif dif > dea:
            macd_score += 3
            details['MACD区域'] = "DIF>DEA但在零轴下(+3)"
        else:
            details['MACD区域'] = "零轴下方(+0)"
        if macd_cross == "金叉":
            macd_score += 10
            details['MACD信号'] = "金叉!(+10)"
        elif macd_bar and macd_bar > 0:
            macd_score += 5
            details['MACD信号'] = f"MACD柱增大(+5)"
        elif macd_cross == "死叉":
            details['MACD信号'] = "死叉(+0)"
        else:
            details['MACD信号'] = "中性(+0)"
        # DIF/DEA差距收窄（潜在金叉）
        if dif and dea and abs(dif - dea) < abs(dif) * 0.1 and dif > dea * 0.9:
            macd_score += 5
            details['MACD趋势'] = "DIF接近DEA，潜在金叉(+5)"
        else:
            details['MACD趋势'] = ""
    total += min(macd_score, 25)
    details['MACD评分'] = f"{min(macd_score, 25):.0f}/25"

    # ---- 量价 (25分) ----
    vol_score = 0.0
    if vol_ratio:
        if vol_ratio >= 2.0:
            vol_score += 12
            details['量比'] = f"{vol_ratio:.1f}x 放量(+12)"
        elif vol_ratio >= 1.2:
            vol_score += 8
            details['量比'] = f"{vol_ratio:.1f}x 温和放量(+8)"
        elif vol_ratio < 0.7:
            vol_score += 2
            details['量比'] = f"{vol_ratio:.1f}x 缩量(+2)"
        else:
            vol_score += 5
            details['量比'] = f"{vol_ratio:.1f}x 正常(+5)"
    if amount_trend and amount_trend > 20:
        vol_score += 8
        details['成交额趋势'] = f"近5日放大{amount_trend:.1f}%(+8)"
    elif amount_trend and amount_trend > 0:
        vol_score += 4
        details['成交额趋势'] = f"近5日微增{amount_trend:.1f}%(+4)"
    else:
        details['成交额趋势'] = f"近5日缩量(+0)"
    if consec_vol_up >= 3:
        vol_score += 5
        details['连续放量'] = f"连续{consec_vol_up}日放量(+5)"
    elif consec_vol_up == 2:
        vol_score += 3
        details['连续放量'] = f"连续{consec_vol_up}日放量(+3)"
    total += min(vol_score, 25)
    details['量价评分'] = f"{min(vol_score, 25):.0f}/25"

    # ---- RSI (10分) ----
    rsi_score = 0.0
    if rsi:
        if 50 <= rsi <= 70:
            rsi_score = 10
            details['RSI'] = f"{rsi:.1f} 强势区间(+10)"
        elif 40 <= rsi < 50:
            rsi_score = 6
            details['RSI'] = f"{rsi:.1f} 中性偏弱(+6)"
        elif rsi > 70:
            rsi_score = 5
            details['RSI'] = f"{rsi:.1f} 超买区间(+5)"
        elif 30 <= rsi < 40:
            rsi_score = 4
            details['RSI'] = f"{rsi:.1f} 弱势(+4)"
        else:
            rsi_score = 2
            details['RSI'] = f"{rsi:.1f} 超卖(+2)"
    total += min(rsi_score, 10)
    details['RSI评分'] = f"{min(rsi_score, 10):.0f}/10"

    return round(min(total, 100), 1), details


# ========== 输出格式 ==========

def score_label(score: float) -> str:
    if score >= 80:
        return "强势 ★★★★★"
    elif score >= 65:
        return "偏强 ★★★★"
    elif score >= 50:
        return "中性 ★★★"
    elif score >= 35:
        return "偏弱 ★★"
    else:
        return "弱势 ★"


def print_analysis(result: dict):
    """打印单只股票分析报告"""
    code = result['code']
    name = result['name']
    price = result['price']
    change_pct = result['change_pct']
    score = result['score']
    details = result['score_details']

    sign = '+' if change_pct >= 0 else ''
    print(f"\n{'='*70}")
    print(f"  {name} ({code})  现价: {price:.2f}  涨跌: {sign}{change_pct:.2f}%")
    print(f"  综合评分: {score:.1f}/100  {score_label(score)}")
    print(f"{'='*70}")

    # 均线
    print(f"\n【均线分析】")
    ma_vals = []
    for k, label in [('ma5', 'MA5'), ('ma10', 'MA10'), ('ma20', 'MA20'), ('ma60', 'MA60')]:
        v = result.get(k)
        if v:
            diff_pct = (price - v) / v * 100
            sign2 = '+' if diff_pct >= 0 else ''
            ma_vals.append(f"{label}:{v:.2f}({sign2}{diff_pct:.1f}%)")
    print(f"  {' | '.join(ma_vals)}")

    # 均线排列
    ma5, ma10, ma20 = result.get('ma5'), result.get('ma10'), result.get('ma20')
    if ma5 and ma10 and ma20:
        if ma5 > ma10 > ma20:
            arrangement = "多头排列 (MA5>MA10>MA20)"
        elif ma5 < ma10 < ma20:
            arrangement = "空头排列 (MA5<MA10<MA20)"
        else:
            arrangement = "均线交叉/混乱"
        print(f"  排列: {arrangement}")
    for k in ['均线排列', 'MA5趋势', 'MA60位置']:
        if details.get(k):
            print(f"  {k}: {details[k]}")
    print(f"  {details.get('均线评分', '')}")

    # MACD
    print(f"\n【MACD分析】")
    dif, dea, macd_bar = result.get('dif'), result.get('dea'), result.get('macd_bar')
    if dif is not None and dea is not None:
        sign_dif = '+' if dif >= 0 else ''
        sign_dea = '+' if dea >= 0 else ''
        sign_bar = '+' if (macd_bar or 0) >= 0 else ''
        cross_str = f"  [{result.get('macd_cross')}!]" if result.get('macd_cross') else ''
        print(f"  DIF: {sign_dif}{dif:.4f}  DEA: {sign_dea}{dea:.4f}  MACD柱: {sign_bar}{(macd_bar or 0):.4f}{cross_str}")
        for k in ['MACD区域', 'MACD信号', 'MACD趋势']:
            if details.get(k):
                print(f"  {k}: {details[k]}")
    print(f"  {details.get('MACD评分', '')}")

    # 量价
    print(f"\n【量价分析】")
    amount = result.get('amount', 0)
    amount_str = f"{amount/1e8:.2f}亿" if amount > 1e6 else f"{amount:.0f}元"
    print(f"  今日成交额: {amount_str}")
    vr = result.get('vol_ratio')
    if vr:
        print(f"  量比: {vr:.2f}x  {details.get('量比', '')}")
    at = result.get('amount_trend')
    if at is not None:
        print(f"  {details.get('成交额趋势', '')}")
    cv = result.get('consec_vol_up', 0)
    if cv > 0:
        print(f"  {details.get('连续放量', '')}")
    print(f"  {details.get('量价评分', '')}")

    # RSI
    rsi = result.get('rsi')
    if rsi:
        print(f"\n【RSI(14)】")
        print(f"  RSI: {rsi:.1f}  {details.get('RSI', '')}")
        print(f"  {details.get('RSI评分', '')}")

    # 操作建议
    print(f"\n【操作建议】")
    advice = gen_advice(result)
    for line in advice:
        print(f"  {line}")

    print()


def gen_advice(result: dict) -> List[str]:
    """根据分析结果生成操作建议"""
    score = result['score']
    change_pct = result.get('change_pct', 0)
    ma5, ma10, ma20 = result.get('ma5'), result.get('ma10'), result.get('ma20')
    price = result['price']
    macd_cross = result.get('macd_cross')
    vol_ratio = result.get('vol_ratio', 1)
    rsi = result.get('rsi')

    advice = []

    if score >= 75:
        advice.append("综合评分较高，技术面偏强，可关注买入机会")
    elif score >= 55:
        advice.append("技术面中性偏强，可观望等待信号确认")
    else:
        advice.append("技术面偏弱，暂不建议追买")

    if macd_cross == "金叉":
        advice.append("MACD金叉，短期上涨动能增强")
    elif macd_cross == "死叉":
        advice.append("MACD死叉，注意回调风险")

    if ma5 and ma10 and ma20:
        if price > ma5 > ma10 > ma20:
            advice.append("多头排列，趋势完整，可持有")
        elif price < ma5 and ma5 < ma10:
            advice.append("价格跌破MA5，需观察是否守住MA10")

    if vol_ratio and vol_ratio >= 2.0 and change_pct > 3:
        advice.append(f"量价配合较好（量比{vol_ratio:.1f}x，涨{change_pct:.1f}%），上涨有效性高")
    elif vol_ratio and vol_ratio >= 2.0 and change_pct < 0:
        advice.append(f"放量下跌（量比{vol_ratio:.1f}x），注意止损")

    if rsi and rsi > 75:
        advice.append(f"RSI={rsi:.0f}，短期超买，注意回调")
    elif rsi and rsi < 30:
        advice.append(f"RSI={rsi:.0f}，超卖，可能存在反弹机会")

    if not advice:
        advice.append("暂无明显信号，继续观察")

    return advice


def save_results_to_csv(results: List[dict], output_dir: str = 'output'):
    """保存分析结果到CSV"""
    os.makedirs(output_dir, exist_ok=True)
    today = date.today().strftime('%Y%m%d')
    path = os.path.join(output_dir, f'analyze_{today}.csv')

    rows = []
    for r in results:
        rows.append({
            '代码': r['code'],
            '名称': r['name'],
            '现价': r['price'],
            '涨跌幅%': r.get('change_pct', 0),
            '综合评分': r['score'],
            '评级': score_label(r['score']).split(' ')[0],
            'MA5': r.get('ma5', ''),
            'MA10': r.get('ma10', ''),
            'MA20': r.get('ma20', ''),
            'MA60': r.get('ma60', ''),
            'DIF': r.get('dif', ''),
            'DEA': r.get('dea', ''),
            'MACD柱': r.get('macd_bar', ''),
            'MACD信号': r.get('macd_cross', ''),
            '量比': r.get('vol_ratio', ''),
            'RSI': r.get('rsi', ''),
            '成交额': r.get('amount', ''),
        })

    df = pd.DataFrame(rows)
    df.to_csv(path, index=False, encoding='utf-8-sig')
    print(f"\n分析结果已保存: {path}")
    return path


# ========== 主流程 ==========

def parse_args():
    parser = argparse.ArgumentParser(
        description='个股技术分析脚本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python analyze.py                           # 使用配置文件中的watchlist
  python analyze.py --codes 688268 688661     # 分析指定股票
  python analyze.py --codes 688268 --days 90  # 分析最近90个交易日
  python analyze.py --codes 688268 --save     # 保存结果到CSV
        """
    )
    parser.add_argument('--codes', nargs='+', help='股票代码列表，例如: 688268 688661')
    parser.add_argument('--days', type=int, default=60, help='分析最近N个交易日数据（默认60）')
    parser.add_argument('--save', action='store_true', help='将结果保存到output目录')
    return parser.parse_args()


def main():
    args = parse_args()
    config = load_config()

    # 确定要分析的股票列表
    codes = []
    if args.codes:
        codes = [c.strip() for c in args.codes]
    else:
        watchlist = config.get('watchlist', {})
        for s in watchlist.get('stocks', []):
            code = str(s.get('code', '')).strip()
            if code:
                codes.append(code)

    if not codes:
        print("错误: 没有要分析的股票。请在 config/settings.yaml 的 watchlist.stocks 中配置，或使用 --codes 参数指定。")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"  个股技术分析")
    print(f"{'='*60}")
    print(f"  分析股票: {codes}")
    print(f"  数据窗口: {args.days} 个交易日")
    print(f"  分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    fetcher_hist = DataFetcher()
    fetcher_rt = RealtimeFetcher()

    results = []
    for i, code in enumerate(codes):
        print(f"\n  [{i+1}/{len(codes)}] 正在分析 {code}...")
        result = analyze_stock(code, fetcher_hist, fetcher_rt, analysis_days=args.days)
        if result:
            results.append(result)
            print_analysis(result)
        time.sleep(0.5)

    if not results:
        print("没有获取到任何股票数据。")
        return

    # 评分汇总
    print(f"\n{'='*70}")
    print(f"  评分汇总 (共分析 {len(results)} 只)")
    print(f"{'='*70}")
    results_sorted = sorted(results, key=lambda x: x['score'], reverse=True)
    for r in results_sorted:
        sign = '+' if r['change_pct'] >= 0 else ''
        print(f"  {r['name']:<10} ({r['code']})  评分: {r['score']:>5.1f}  {score_label(r['score'])}  "
              f"现价: {r['price']:.2f} ({sign}{r['change_pct']:.2f}%)")
    print()

    if args.save:
        save_results_to_csv(results)


if __name__ == '__main__':
    main()
