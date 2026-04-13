"""实时行情获取模块"""
import requests
import re
from typing import Dict, List, Optional, Literal
from dataclasses import dataclass
from datetime import datetime


@dataclass
class RealtimeQuote:
    """实时行情数据类"""
    code: str
    name: str
    price: float
    open: float
    high: float
    low: float
    pre_close: float
    volume: int  # 成交量（手）
    amount: float  # 成交额（元）
    change_amt: float  # 涨跌额
    change_pct: float  # 涨跌幅(%)
    turnover: Optional[float] = None  # 换手率
    bid1: float = 0  # 买一价
    ask1: float = 0  # 卖一价
    bid1_vol: int = 0  # 买一量
    ask1_vol: int = 0  # 卖一量
    timestamp: datetime = None

    def to_dict(self) -> Dict:
        return {
            'code': self.code,
            'name': self.name,
            'price': self.price,
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'pre_close': self.pre_close,
            'volume': self.volume,
            'amount': self.amount,
            'change_amt': self.change_amt,
            'change_pct': self.change_pct,
            'turnover': self.turnover,
            'bid1': self.bid1,
            'ask1': self.ask1,
            'bid1_vol': self.bid1_vol,
            'ask1_vol': self.ask1_vol,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }


class RealtimeFetcher:
    """实时行情获取器 - 使用新浪财经接口"""

    # 新浪财经实时行情接口
    SINA_API = "http://hq.sinajs.cn/list={}"

    # 请求头
    HEADERS = {
        'Referer': 'http://finance.sina.com.cn',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    def _get_market_prefix(self, code: str) -> str:
        """根据代码判断市场前缀"""
        if code.startswith('6'):
            return 'sh'  # 沪市
        elif code.startswith(('0', '3')):
            return 'sz'  # 深市
        elif code.startswith(('4', '8')):
            return 'bj'  # 北交所
        else:
            return 'sh'  # 默认沪市

    def _parse_sina_data(self, response_text: str) -> List[RealtimeQuote]:
        """解析新浪接口返回的数据"""
        quotes = []

        # 正则匹配: var hq_str_sh600789="xxx,xxx,..."
        pattern = r'var hq_str_(\w+)="(.*)";'
        matches = re.findall(pattern, response_text)

        for symbol, data in matches:
            if not data:  # 空数据跳过
                continue

            fields = data.split(',')
            if len(fields) < 32:
                continue

            try:
                code = symbol[2:]  # 去掉市场前缀
                name = fields[0]
                open_price = float(fields[1]) if fields[1] else 0
                pre_close = float(fields[2]) if fields[2] else 0
                price = float(fields[3]) if fields[3] else 0
                high = float(fields[4]) if fields[4] else 0
                low = float(fields[5]) if fields[5] else 0
                volume = int(float(fields[8])) if fields[8] else 0
                amount = float(fields[9]) if fields[9] else 0

                # 买卖盘
                bid1 = float(fields[10]) if fields[10] else 0
                ask1 = float(fields[20]) if fields[20] else 0
                bid1_vol = int(float(fields[11])) if fields[11] else 0
                ask1_vol = int(float(fields[21])) if fields[21] else 0

                # 日期时间
                date_str = fields[30]
                time_str = fields[31]
                timestamp = None
                if date_str and time_str:
                    try:
                        timestamp = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
                    except:
                        timestamp = datetime.now()

                change_amt = price - pre_close if price and pre_close else 0
                change_pct = (change_amt / pre_close * 100) if pre_close else 0

                quote = RealtimeQuote(
                    code=code,
                    name=name,
                    price=price,
                    open=open_price,
                    high=high,
                    low=low,
                    pre_close=pre_close,
                    volume=volume,
                    amount=amount,
                    change_amt=change_amt,
                    change_pct=change_pct,
                    bid1=bid1,
                    ask1=ask1,
                    bid1_vol=bid1_vol,
                    ask1_vol=ask1_vol,
                    timestamp=timestamp
                )
                quotes.append(quote)

            except (ValueError, IndexError) as e:
                continue

        return quotes

    def get_quote(self, code: str) -> Optional[RealtimeQuote]:
        """获取单只股票实时行情"""
        quotes = self.get_quotes([code])
        return quotes[0] if quotes else None

    def get_quotes(self, codes: List[str]) -> List[RealtimeQuote]:
        """批量获取实时行情"""
        # 构建请求代码列表
        symbols = [f"{self._get_market_prefix(c)}{c}" for c in codes]
        symbol_str = ','.join(symbols)

        url = self.SINA_API.format(symbol_str)

        try:
            response = self.session.get(url, timeout=10)
            response.encoding = 'gbk'
            return self._parse_sina_data(response.text)
        except Exception as e:
            print(f"获取实时行情失败: {e}")
            return []

    def get_minute_data(self, code: str) -> List[Dict]:
        """获取分时数据"""
        market = self._get_market_prefix(code)
        market_code = 1 if market == 'sh' else 0  # 东财接口: 1=沪市, 0=深市/北交所

        # 东方财富分时接口
        url = f"http://push2his.eastmoney.com/api/qt/stock/kline/get"
        params = {
            'secid': f'{market_code}.{code}',
            'fields1': 'f1,f2,f3,f4,f5,f6',
            'fields2': 'f51,f52,f53,f54,f55,f56,f57',
            'klt': 101,  # 分时
            'fqt': 1,
            'end': '20500000',
            'lmt': 240  # 最近240条（一天）
        }

        try:
            response = requests.get(url, params=params, timeout=10)
            data = response.json()

            if data.get('data') and data['data'].get('klines'):
                result = []
                for line in data['data']['klines']:
                    parts = line.split(',')
                    if len(parts) >= 6:
                        result.append({
                            'time': parts[0],
                            'price': float(parts[1]),
                            'volume': int(float(parts[2])),
                            'amount': float(parts[3]),
                            'high': float(parts[4]),
                            'low': float(parts[5])
                        })
                return result
        except Exception as e:
            print(f"获取分时数据失败: {e}")

        return []

    def print_quote(self, quote: RealtimeQuote):
        """格式化输出行情"""
        change_sign = '+' if quote.change_amt >= 0 else ''
        print(f"\n{'='*60}")
        print(f"股票: {quote.name} ({quote.code})")
        print(f"{'='*60}")
        print(f"\n【实时行情】")
        print(f"  现价: {quote.price:.2f}  涨跌: {change_sign}{quote.change_pct:.2f}%")
        print(f"  今开: {quote.open:.2f}  最高: {quote.high:.2f}  最低: {quote.low:.2f}")
        print(f"  昨收: {quote.pre_close:.2f}")
        print(f"  成交量: {quote.volume/10000:.2f}万手  成交额: {quote.amount/100000000:.2f}亿")
        if quote.bid1 > 0:
            print(f"  买一: {quote.bid1:.2f} ({quote.bid1_vol}手)  卖一: {quote.ask1:.2f} ({quote.ask1_vol}手)")
        if quote.timestamp:
            print(f"  更新时间: {quote.timestamp.strftime('%H:%M:%S')}")
        print()


# 便捷函数
def get_realtime_quote(code: str) -> Optional[RealtimeQuote]:
    """获取单只股票实时行情"""
    fetcher = RealtimeFetcher()
    return fetcher.get_quote(code)


def get_realtime_quotes(codes: List[str]) -> List[RealtimeQuote]:
    """批量获取实时行情"""
    fetcher = RealtimeFetcher()
    return fetcher.get_quotes(codes)
