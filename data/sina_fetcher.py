"""新浪财经数据获取模块（备用）"""
import urllib.request
import json
import re
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional


class SinaDataFetcher:
    """使用新浪财经接口获取股票数据"""
    
    def get_a_share_daily(self, 
                          symbol: str, 
                          start_date: Optional[str] = None,
                          end_date: Optional[str] = None) -> pd.DataFrame:
        """获取A股日线数据（新浪财经日K线接口）"""
        if end_date is None:
            end_date = datetime.now().strftime('%Y%m%d')
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')
        
        start_date = start_date.replace('-', '')
        end_date = end_date.replace('-', '')
        
        # 新浪财经格式代码
        if symbol.startswith('6') or symbol.startswith('688'):
            sina_symbol = 'sh' + symbol
        elif symbol.startswith('8') or symbol.startswith('4'):
            sina_symbol = 'bj' + symbol
        else:
            sina_symbol = 'sz' + symbol
        
        # 新浪财经日K线接口 (scale=240表示日线, datalen=60表示60个交易日)
        url = f"https://quotes.sina.cn/cn/api/jsonp_v2.php/var_{sina_symbol}=/CN_MarketDataService.getKLineData?symbol={sina_symbol}&scale=240&ma=no&datalen=60"
        
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://finance.sina.com.cn',
            })
            
            resp = urllib.request.urlopen(req, timeout=15)
            text = resp.read().decode('utf-8')
            
            # 解析JSONP: var_xxx=([...])
            match = re.search(r'\(\[(.*)\]\)', text, re.DOTALL)
            if not match:
                raise ValueError(f"无法解析数据: {symbol}")
            
            data = json.loads('[' + match.group(1) + ']')
            
            rows = []
            for item in data:
                date_str = item['day']
                # 过滤日期范围
                item_date = date_str.replace('-', '')
                if start_date <= item_date <= end_date:
                    rows.append({
                        'date': date_str,
                        'open': float(item['open']),
                        'high': float(item['high']),
                        'low': float(item['low']),
                        'close': float(item['close']),
                        'volume': float(item['volume']),
                    })
            
            if rows:
                df = pd.DataFrame(rows)
                df['date'] = pd.to_datetime(df['date'])
                df = df.sort_values('date').reset_index(drop=True)
                df['amount'] = 0  # 新浪接口不提供成交额
                return df
            
            raise ValueError(f"未获取到数据: {symbol}")
            
        except Exception as e:
            print(f"新浪财经获取失败: {e}")
            raise


# 测试
if __name__ == '__main__':
    fetcher = SinaDataFetcher()
    df = fetcher.get_a_share_daily('688258', '20260303', '20260403')
    print(df)
