"""数据获取模块 - 支持A股、港股、美股"""
import akshare as ak
import yfinance as yf
import pandas as pd
import urllib.request
import urllib.parse
import json
import re
from datetime import datetime, timedelta
from typing import Optional, Literal


class DataFetcher:
    """统一数据获取接口"""
    
    def __init__(self):
        self.retry_times = 3
        self.retry_delay = 1
    
    def get_a_share_daily(self, 
                          symbol: str, 
                          start_date: Optional[str] = None,
                          end_date: Optional[str] = None,
                          adjust: str = "qfq") -> pd.DataFrame:
        """获取A股日线数据"""
        if end_date is None:
            end_date = datetime.now().strftime('%Y%m%d')
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')
        
        start_date = start_date.replace('-', '')
        end_date = end_date.replace('-', '')
        
        # 先尝试 AKShare
        try:
            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust=adjust
            )
            return self._standardize_columns(df, 'a_share')
        except Exception as e:
            print(f"AKShare获取失败，使用新浪财经备用接口")
            return self._get_a_share_daily_sina(symbol, start_date, end_date)
    
    def _get_a_share_daily_sina(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """备用：从新浪财经获取A股日线数据"""
        # 新浪财经格式代码
        if symbol.startswith('6') or symbol.startswith('688'):
            sina_symbol = 'sh' + symbol
        elif symbol.startswith('8') or symbol.startswith('4'):
            sina_symbol = 'bj' + symbol
        else:
            sina_symbol = 'sz' + symbol
        
        # 新浪财经日K线接口
        url = f"https://quotes.sina.cn/cn/api/jsonp_v2.php/var_{sina_symbol}=/CN_MarketDataService.getKLineData?symbol={sina_symbol}&scale=240&ma=no&datalen=60"
        
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://finance.sina.com.cn',
        })
        
        resp = urllib.request.urlopen(req, timeout=15)
        text = resp.read().decode('utf-8')
        
        # 解析JSONP
        match = re.search(r'\(\[(.*)\]\)', text, re.DOTALL)
        if not match:
            raise ValueError(f"无法解析数据: {symbol}")
        
        data = json.loads('[' + match.group(1) + ']')
        
        rows = []
        for item in data:
            date_str = item['day']
            item_date = date_str.replace('-', '')
            if start_date <= item_date <= end_date:
                rows.append({
                    'date': date_str,
                    'open': float(item['open']),
                    'high': float(item['high']),
                    'low': float(item['low']),
                    'close': float(item['close']),
                    'volume': float(item['volume']),
                    'amount': 0,
                })
        
        if not rows:
            raise ValueError(f"未获取到数据: {symbol}")
        
        df = pd.DataFrame(rows)
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)
        return df
    
    def get_hk_stock_daily(self,
                           symbol: str,
                           start_date: Optional[str] = None,
                           end_date: Optional[str] = None,
                           adjust: str = "qfq") -> pd.DataFrame:
        """获取港股日线数据"""
        if end_date is None:
            end_date = datetime.now().strftime('%Y%m%d')
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')
        
        start_date = start_date.replace('-', '')
        end_date = end_date.replace('-', '')
        
        df = ak.stock_hk_hist(
            symbol=symbol,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust=adjust
        )
        
        return self._standardize_columns(df, 'hk_share')
    
    def get_us_stock_daily(self,
                           symbol: str,
                           start_date: Optional[str] = None,
                           end_date: Optional[str] = None) -> pd.DataFrame:
        """获取美股日线数据"""
        ticker = yf.Ticker(symbol)
        
        df = ticker.history(start=start_date, end=end_date)
        df = df.reset_index()
        df = self._standardize_columns(df, 'us_share')
        df['symbol'] = symbol
        
        return df
    
    def get_stock_data(self,
                       symbol: str,
                       market: Literal['a_share', 'hk_share', 'us_share'],
                       start_date: Optional[str] = None,
                       end_date: Optional[str] = None,
                       **kwargs) -> pd.DataFrame:
        """统一接口获取股票数据"""
        if market == 'a_share':
            return self.get_a_share_daily(symbol, start_date, end_date, **kwargs)
        elif market == 'hk_share':
            return self.get_hk_stock_daily(symbol, start_date, end_date, **kwargs)
        elif market == 'us_share':
            return self.get_us_stock_daily(symbol, start_date, end_date, **kwargs)
        else:
            raise ValueError(f"不支持的市场类型: {market}")
    
    def _standardize_columns(self, df: pd.DataFrame, market: str) -> pd.DataFrame:
        """标准化列名"""
        column_mapping = {
            '日期': 'date',
            '开盘': 'open',
            '收盘': 'close',
            '最高': 'high',
            '最低': 'low',
            '成交量': 'volume',
            '成交额': 'amount',
            '涨跌幅': 'change_pct',
            'Date': 'date',
            'Open': 'open',
            'High': 'high',
            'Low': 'low',
            'Close': 'close',
            'Volume': 'volume',
        }
        
        df = df.rename(columns=column_mapping)
        
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date').reset_index(drop=True)
        
        return df
