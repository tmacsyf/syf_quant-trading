"""
盯盘脚本 - 实时监控指定股票
功能:
  - 1分钟刷新一次实时行情
  - 均线突破提醒 (MA5/MA10/MA20)
  - 量比超阈值告警
  - 涨跌幅超阈值告警
  - 持仓成本/止损/止盈价位触碰告警
  - 飞书通知推送

用法:
  python monitor.py                          # 使用配置文件中的watchlist
  python monitor.py --codes 688268 688661    # 指定股票代码
  python monitor.py --codes 688268 --cost 50.0 --stop-loss 45.0 --stop-profit 60.0
"""

import sys
import os
import io
import time
import json
import argparse
import requests
import pandas as pd

# 修复 Windows 终端中文输出乱码
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
import numpy as np
from datetime import datetime, date
from typing import List, Dict, Optional, Tuple
import yaml

# 项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from data.realtime import RealtimeFetcher, RealtimeQuote
from data.fetcher import DataFetcher

# ========== 配置加载 ==========

def load_config() -> dict:
    """加载配置文件"""
    config_path = os.path.join(os.path.dirname(__file__), 'config', 'settings.yaml')
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"[警告] 配置文件加载失败: {e}")
        return {}


# ========== 飞书通知 ==========

class FeishuNotifier:
    """飞书自定义机器人通知"""

    def __init__(self, webhook_url: str, enabled: bool = True):
        self.webhook_url = webhook_url
        self.enabled = enabled and bool(webhook_url)
        self._last_alerts: Dict[str, float] = {}  # 防止重复告警: key -> timestamp
        self.alert_cooldown = 300  # 同一告警5分钟内不重复

    def _should_alert(self, alert_key: str) -> bool:
        """检查是否应该发送告警（防抖）"""
        now = time.time()
        last = self._last_alerts.get(alert_key, 0)
        if now - last >= self.alert_cooldown:
            self._last_alerts[alert_key] = now
            return True
        return False

    def send(self, title: str, content: str, alert_key: str = None) -> bool:
        """发送飞书消息"""
        if not self.enabled:
            return False

        if alert_key and not self._should_alert(alert_key):
            return False  # 冷却中，跳过

        payload = {
            "msg_type": "post",
            "content": {
                "post": {
                    "zh_cn": {
                        "title": title,
                        "content": [[{"tag": "text", "text": content}]]
                    }
                }
            }
        }

        try:
            resp = requests.post(
                self.webhook_url,
                json=payload,
                timeout=5
            )
            result = resp.json()
            if result.get("StatusCode") == 0 or result.get("code") == 0:
                return True
            else:
                print(f"  [飞书] 发送失败: {result}")
                return False
        except Exception as e:
            print(f"  [飞书] 请求异常: {e}")
            return False

    def send_alert(self, code: str, name: str, alert_type: str, detail: str):
        """发送告警消息"""
        now_str = datetime.now().strftime("%H:%M:%S")
        title = f"【盯盘告警】{name}({code})"
        content = f"时间: {now_str}\n类型: {alert_type}\n详情: {detail}"
        alert_key = f"{code}_{alert_type}"
        sent = self.send(title, content, alert_key)
        if sent:
            print(f"  [飞书告警已发送] {name}({code}) - {alert_type}")


# ========== 技术指标计算 ==========

def fetch_ma_data(code: str, fetcher: DataFetcher) -> Dict:
    """获取历史数据并计算MA5/MA10/MA20"""
    try:
        df = fetcher.get_a_share_daily(code, start_date='2025-01-01')
        if df is None or len(df) < 20:
            return {}

        # 确保按日期排序
        if '日期' in df.columns:
            df = df.sort_values('日期').reset_index(drop=True)
        elif 'date' in df.columns:
            df = df.sort_values('date').reset_index(drop=True)

        # 获取收盘价列
        close_col = None
        for col in ['收盘', 'close', '收盘价']:
            if col in df.columns:
                close_col = col
                break
        vol_col = None
        for col in ['成交量', 'volume', 'vol']:
            if col in df.columns:
                vol_col = col
                break

        if close_col is None:
            return {}

        closes = df[close_col].astype(float).values
        ma5 = float(np.mean(closes[-5:])) if len(closes) >= 5 else None
        ma10 = float(np.mean(closes[-10:])) if len(closes) >= 10 else None
        ma20 = float(np.mean(closes[-20:])) if len(closes) >= 20 else None

        # 量比 = 今日量 / 过去5日平均量
        avg_vol_5 = None
        if vol_col:
            vols = df[vol_col].astype(float).values
            if len(vols) >= 6:
                avg_vol_5 = float(np.mean(vols[-6:-1]))  # 过去5日（不含今日）

        return {
            'ma5': ma5,
            'ma10': ma10,
            'ma20': ma20,
            'avg_vol_5': avg_vol_5,
            'prev_closes': closes[-3:].tolist() if len(closes) >= 3 else closes.tolist(),
        }
    except Exception as e:
        return {}


# ========== 告警检测 ==========

def check_alerts(
    quote: RealtimeQuote,
    ma_data: dict,
    stock_cfg: dict,
    alert_cfg: dict,
    notifier: FeishuNotifier,
) -> List[str]:
    """
    检测各类告警，返回触发的告警描述列表
    """
    alerts = []
    code = quote.code
    name = quote.name

    # 1. 涨幅告警
    rise_thr = alert_cfg.get('rise_pct_threshold', 7.0)
    drop_thr = alert_cfg.get('drop_pct_threshold', -5.0)
    if quote.change_pct >= rise_thr:
        msg = f"涨幅 {quote.change_pct:.2f}% >= {rise_thr}%"
        alerts.append(f"[涨幅] {msg}")
        notifier.send_alert(code, name, "涨幅告警", f"现价 {quote.price:.2f}，{msg}")
    if quote.change_pct <= drop_thr:
        msg = f"跌幅 {quote.change_pct:.2f}% <= {drop_thr}%"
        alerts.append(f"[跌幅] {msg}")
        notifier.send_alert(code, name, "跌幅告警", f"现价 {quote.price:.2f}，{msg}")

    # 2. 量比告警
    vol_thr = alert_cfg.get('volume_ratio_threshold', 3.0)
    if ma_data.get('avg_vol_5') and ma_data['avg_vol_5'] > 0 and quote.volume > 0:
        # 量比 = 当前成交量 / (5日平均量 * 今日已过交易时间比)
        # 简化：直接用当前成交量 vs 5日平均量
        vol_ratio = quote.volume / ma_data['avg_vol_5']
        if vol_ratio >= vol_thr:
            msg = f"量比 {vol_ratio:.2f}x >= {vol_thr}x"
            alerts.append(f"[量比] {msg}")
            notifier.send_alert(code, name, "量比异常", f"现价 {quote.price:.2f}，{msg}")

    # 3. MA突破告警
    price = quote.price
    prev_closes = ma_data.get('prev_closes', [])
    prev_price = prev_closes[-1] if prev_closes else None

    for ma_name, ma_val in [('MA5', ma_data.get('ma5')), ('MA10', ma_data.get('ma10')), ('MA20', ma_data.get('ma20'))]:
        if ma_val is None:
            continue
        # 向上突破：前收盘 < MA，现价 >= MA
        if prev_price and prev_price < ma_val and price >= ma_val:
            msg = f"价格向上突破 {ma_name} ({ma_val:.2f})"
            alerts.append(f"[均线] {msg}")
            notifier.send_alert(code, name, f"向上突破{ma_name}", f"现价 {price:.2f}，{msg}")
        # 向下跌破：前收盘 > MA，现价 < MA
        elif prev_price and prev_price > ma_val and price < ma_val:
            msg = f"价格向下跌破 {ma_name} ({ma_val:.2f})"
            alerts.append(f"[均线] {msg}")
            notifier.send_alert(code, name, f"向下跌破{ma_name}", f"现价 {price:.2f}，{msg}")

    # 4. 持仓价位告警
    cost_price = stock_cfg.get('cost_price', 0)
    stop_loss = stock_cfg.get('stop_loss', 0)
    stop_profit = stock_cfg.get('stop_profit', 0)

    if stop_loss > 0 and price <= stop_loss:
        msg = f"现价 {price:.2f} <= 止损价 {stop_loss:.2f}"
        alerts.append(f"[止损] {msg}")
        notifier.send_alert(code, name, "触及止损价", msg)

    if stop_profit > 0 and price >= stop_profit:
        msg = f"现价 {price:.2f} >= 止盈价 {stop_profit:.2f}"
        alerts.append(f"[止盈] {msg}")
        notifier.send_alert(code, name, "触及止盈价", msg)

    if cost_price > 0:
        pnl_pct = (price - cost_price) / cost_price * 100
        # 浮亏超过 5% 也提醒
        if pnl_pct <= -5.0:
            msg = f"持仓浮亏 {pnl_pct:.2f}%，现价 {price:.2f}，成本 {cost_price:.2f}"
            alerts.append(f"[浮亏] {msg}")
            notifier.send_alert(code, name, "持仓浮亏告警", msg)

    return alerts


# ========== 显示逻辑 ==========

def get_trend_arrow(pct: float) -> str:
    if pct > 3:
        return "↑↑"
    elif pct > 0:
        return "↑"
    elif pct < -3:
        return "↓↓"
    elif pct < 0:
        return "↓"
    return "-"


def ma_position_label(price: float, ma5: float, ma10: float, ma20: float) -> str:
    """价格相对均线位置"""
    if price > ma5 > ma10 > ma20:
        return "多头排列"
    elif price < ma5 < ma10 < ma20:
        return "空头排列"
    elif price > ma5:
        return "站上MA5"
    elif price > ma10:
        return "站上MA10"
    elif price > ma20:
        return "站上MA20"
    else:
        return "低于MA20"


def print_monitor_table(results: List[dict], refresh_count: int):
    """打印盯盘面板"""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    os.system('cls' if os.name == 'nt' else 'clear')

    print(f"{'='*90}")
    print(f"  盯盘监控  |  更新时间: {now_str}  |  第 {refresh_count} 次刷新")
    print(f"{'='*90}")
    header = f"{'代码':<8} {'名称':<10} {'现价':>8} {'涨跌%':>8} {'趋势':>4} {'成交额':>10} {'量比':>6} {'MA5':>8} {'MA10':>8} {'MA20':>8} {'均线位置':<10}"
    print(header)
    print(f"{'-'*90}")

    for r in results:
        q = r['quote']
        ma = r['ma_data']
        cfg = r['stock_cfg']
        alerts = r['alerts']

        pct_str = f"{q.change_pct:+.2f}%"
        arrow = get_trend_arrow(q.change_pct)
        amount_str = f"{q.amount/1e8:.2f}亿" if q.amount > 0 else "-"

        vol_ratio_str = "-"
        if ma.get('avg_vol_5') and ma['avg_vol_5'] > 0 and q.volume > 0:
            vol_ratio = q.volume / ma['avg_vol_5']
            vol_ratio_str = f"{vol_ratio:.1f}x"

        ma5 = ma.get('ma5')
        ma10 = ma.get('ma10')
        ma20 = ma.get('ma20')
        ma5_str = f"{ma5:.2f}" if ma5 else "-"
        ma10_str = f"{ma10:.2f}" if ma10 else "-"
        ma20_str = f"{ma20:.2f}" if ma20 else "-"

        ma_label = "-"
        if ma5 and ma10 and ma20:
            ma_label = ma_position_label(q.price, ma5, ma10, ma20)

        row = (f"{q.code:<8} {q.name:<10} {q.price:>8.2f} {pct_str:>8} {arrow:>4} "
               f"{amount_str:>10} {vol_ratio_str:>6} {ma5_str:>8} {ma10_str:>8} {ma20_str:>8} {ma_label:<10}")
        print(row)

        # 持仓信息
        cost = cfg.get('cost_price', 0)
        sl = cfg.get('stop_loss', 0)
        sp = cfg.get('stop_profit', 0)
        if cost > 0:
            pnl = (q.price - cost) / cost * 100
            pnl_str = f"{pnl:+.2f}%"
            extra = f"  成本:{cost:.2f} 浮盈:{pnl_str}"
            if sl > 0:
                extra += f" 止损:{sl:.2f}"
            if sp > 0:
                extra += f" 止盈:{sp:.2f}"
            print(f"  {' '*8}  {extra}")

        # 触发的告警
        if alerts:
            for a in alerts:
                print(f"  *** {a}")

    print(f"{'='*90}")
    print(f"  [飞书告警] {'已启用' if results and results[0].get('notifier_enabled') else '未启用'}  |  Ctrl+C 退出")
    print(f"{'='*90}")


# ========== 主逻辑 ==========

def build_watch_stocks(args, config: dict) -> List[dict]:
    """构建监控股票列表"""
    stocks = []

    if args.codes:
        # 命令行模式：可以传多个code，但只有第一个支持成本/止损/止盈
        for i, code in enumerate(args.codes):
            s = {'code': code.strip(), 'name': code.strip(), 'cost_price': 0, 'stop_loss': 0, 'stop_profit': 0}
            if i == 0:
                if args.cost:
                    s['cost_price'] = args.cost
                if args.stop_loss:
                    s['stop_loss'] = args.stop_loss
                if args.stop_profit:
                    s['stop_profit'] = args.stop_profit
            stocks.append(s)
    else:
        # 配置文件模式
        watchlist = config.get('watchlist', {})
        cfg_stocks = watchlist.get('stocks', [])
        for s in cfg_stocks:
            stocks.append({
                'code': str(s.get('code', '')).strip(),
                'name': str(s.get('name', '')).strip(),
                'cost_price': float(s.get('cost_price', 0) or 0),
                'stop_loss': float(s.get('stop_loss', 0) or 0),
                'stop_profit': float(s.get('stop_profit', 0) or 0),
            })

    return [s for s in stocks if s['code']]


def is_trading_time() -> bool:
    """判断是否在交易时间（9:25-11:30, 13:00-15:05）"""
    now = datetime.now()
    if now.weekday() >= 5:  # 周末
        return False
    t = now.hour * 60 + now.minute
    morning = (9 * 60 + 25) <= t <= (11 * 60 + 30)
    afternoon = (13 * 60) <= t <= (15 * 60 + 5)
    return morning or afternoon


def run_monitor(stocks: List[dict], alert_cfg: dict, notifier: FeishuNotifier,
                interval: int = 60, force_run: bool = False):
    """主监控循环"""
    fetcher_rt = RealtimeFetcher()
    fetcher_hist = DataFetcher()
    codes = [s['code'] for s in stocks]
    stock_map = {s['code']: s for s in stocks}

    # 预加载MA数据（每次刷新都重新算，避免日内不更新）
    print(f"正在加载 {len(codes)} 只股票的历史数据...")
    ma_cache: Dict[str, dict] = {}
    for code in codes:
        ma_cache[code] = fetch_ma_data(code, fetcher_hist)
        time.sleep(0.3)
    print("历史数据加载完成，开始监控...\n")

    refresh_count = 0
    last_ma_refresh = time.time()

    try:
        while True:
            now = datetime.now()

            # 非交易时间提示（非强制运行模式）
            if not force_run and not is_trading_time():
                print(f"[{now.strftime('%H:%M:%S')}] 当前非交易时间，等待中... (Ctrl+C 退出)")
                time.sleep(30)
                continue

            # 每30分钟刷新一次MA数据
            if time.time() - last_ma_refresh > 1800:
                for code in codes:
                    ma_cache[code] = fetch_ma_data(code, fetcher_hist)
                    time.sleep(0.2)
                last_ma_refresh = time.time()

            # 获取实时行情
            quotes = fetcher_rt.get_quotes(codes)
            quote_map = {q.code: q for q in quotes}

            refresh_count += 1
            results = []

            for s in stocks:
                code = s['code']
                q = quote_map.get(code)
                if q is None:
                    # 找不到行情时用占位
                    continue
                # 用股票配置中的名称（如果有）
                if s.get('name') and s['name'] != code:
                    q.name = s['name']

                ma = ma_cache.get(code, {})
                alerts = check_alerts(q, ma, s, alert_cfg, notifier)

                results.append({
                    'quote': q,
                    'ma_data': ma,
                    'stock_cfg': s,
                    'alerts': alerts,
                    'notifier_enabled': notifier.enabled,
                })

            print_monitor_table(results, refresh_count)

            # 等待下次刷新
            time.sleep(interval)

    except KeyboardInterrupt:
        print("\n\n已退出盯盘监控。")


# ========== 入口 ==========

def parse_args():
    parser = argparse.ArgumentParser(
        description='盯盘脚本 - 实时监控指定股票',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python monitor.py                              # 使用配置文件中的watchlist
  python monitor.py --codes 688268 688661        # 监控指定股票
  python monitor.py --codes 688268 --cost 50.0 --stop-loss 45.0 --stop-profit 60.0
  python monitor.py --codes 688268 --interval 30 # 30秒刷新一次
  python monitor.py --force                      # 非交易时间也运行
        """
    )
    parser.add_argument('--codes', nargs='+', help='股票代码列表，例如: 688268 688661')
    parser.add_argument('--cost', type=float, help='持仓成本价（仅对第一个code生效）')
    parser.add_argument('--stop-loss', type=float, dest='stop_loss', help='止损价')
    parser.add_argument('--stop-profit', type=float, dest='stop_profit', help='止盈价')
    parser.add_argument('--interval', type=int, default=60, help='刷新间隔秒数（默认60）')
    parser.add_argument('--force', action='store_true', help='非交易时间也运行（用于测试）')
    parser.add_argument('--volume-threshold', type=float, dest='volume_threshold',
                        help='量比告警阈值（覆盖配置文件）')
    parser.add_argument('--rise-threshold', type=float, dest='rise_threshold',
                        help='涨幅告警阈值（覆盖配置文件）')
    return parser.parse_args()


def main():
    args = parse_args()
    config = load_config()

    # 构建监控股票列表
    stocks = build_watch_stocks(args, config)
    if not stocks:
        print("错误: 没有要监控的股票。请在 config/settings.yaml 的 watchlist.stocks 中配置，或使用 --codes 参数指定。")
        sys.exit(1)

    # 告警配置
    watchlist_cfg = config.get('watchlist', {})
    alert_cfg = watchlist_cfg.get('alert', {
        'volume_ratio_threshold': 3.0,
        'rise_pct_threshold': 7.0,
        'drop_pct_threshold': -5.0,
    })
    # 命令行覆盖
    if args.volume_threshold:
        alert_cfg['volume_ratio_threshold'] = args.volume_threshold
    if args.rise_threshold:
        alert_cfg['rise_pct_threshold'] = args.rise_threshold

    # 飞书通知
    monitor_cfg = config.get('monitor', {})
    feishu_cfg = monitor_cfg.get('feishu', {})
    webhook_url = feishu_cfg.get('webhook_url', '')
    feishu_enabled = feishu_cfg.get('enabled', False)
    notifier = FeishuNotifier(webhook_url=webhook_url, enabled=feishu_enabled)

    print(f"\n{'='*60}")
    print(f"  盯盘监控启动")
    print(f"{'='*60}")
    print(f"  监控股票: {[s['code'] for s in stocks]}")
    print(f"  刷新间隔: {args.interval} 秒")
    print(f"  量比阈值: {alert_cfg['volume_ratio_threshold']}x")
    print(f"  涨幅阈值: {alert_cfg['rise_pct_threshold']}%")
    print(f"  跌幅阈值: {alert_cfg['drop_pct_threshold']}%")
    print(f"  飞书告警: {'已启用' if notifier.enabled else '未启用（请配置 webhook_url）'}")
    print(f"{'='*60}\n")

    run_monitor(
        stocks=stocks,
        alert_cfg=alert_cfg,
        notifier=notifier,
        interval=args.interval,
        force_run=args.force,
    )


if __name__ == '__main__':
    main()
