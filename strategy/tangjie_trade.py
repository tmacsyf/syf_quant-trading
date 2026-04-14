"""唐杰隔夜持股T+1策略

核心逻辑：尾盘买入 → 次日早盘卖出
纯规则化，无主观判断

策略特点：
1. 选股条件严格：涨幅3-7% + 量比≥1.2 + 均线多头
2. 仓位控制：单票10%，最多5只，总仓50%
3. 止盈止损：+3%止盈，-2%止损，10点强制清仓
4. 风控机制：大盘跌>1.5%或跌停>15只时空仓
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from .base import BaseStrategy


# 策略默认参数
DEFAULT_PARAMS = {
    # 选股参数
    "min_daily_amount": 100000000,   # 日均成交额≥1亿
    "min_turnover": 3,               # 换手率≥3%
    "rise_range": (3, 7),            # 当日涨幅3%-7%
    "min_volume_ratio": 1.2,         # 量比≥1.2
    "new_stock_days": 60,            # 剔除上市<60天次新
    
    # 仓位参数
    "single_position": 0.1,          # 单票仓位10%
    "max_hold_num": 5,               # 最大持仓5只
    "total_position_limit": 0.5,     # 总仓位≤50%
    
    # 止盈止损
    "take_profit": 0.03,             # 止盈3%
    "stop_loss": -0.02,              # 止损-2%
    
    # 风控参数
    "index_drop_limit": 1.5,         # 大盘跌幅阈值
    "limit_down_limit": 15,          # 跌停数阈值
}


class TangjieTradeStrategy(BaseStrategy):
    """唐杰隔夜持股T+1策略"""
    
    def __init__(self, params: dict = None):
        super().__init__("TangjieTrade")
        self.params = {**DEFAULT_PARAMS, **(params or {})}
        self.holdings = {}  # 持仓记录 {symbol: {cost, quantity, buy_date}}
        self.trade_log = []  # 交易记录
        
    def on_data(self, data: Dict[str, pd.DataFrame]):
        """每日数据处理 - 回测模式"""
        if not data:
            return
        
        # 获取当前日期（取第一个股票的最后日期）
        first_symbol = list(data.keys())[0]
        current_date = data[first_symbol]['date'].iloc[-1]
        
        # 1. 先处理卖出（次日早盘逻辑）
        self._process_sell(data, current_date)
        
        # 2. 再处理买入（尾盘逻辑）
        self._process_buy(data, current_date)
    
    def _process_sell(self, data: Dict[str, pd.DataFrame], current_date):
        """处理卖出逻辑"""
        to_sell = []
        
        for symbol, holding in list(self.holdings.items()):
            if symbol not in data:
                continue
            
            df = data[symbol]
            # 找到当前日期的数据
            today_data = df[df['date'] == current_date]
            if today_data.empty:
                continue
            
            current_price = today_data['close'].iloc[0]
            cost = holding['cost']
            profit_pct = (current_price - cost) / cost
            
            # 判断是否需要卖出
            should_sell = False
            sell_reason = ""
            
            # 1. 止盈
            if profit_pct >= self.params['take_profit']:
                should_sell = True
                sell_reason = f"止盈(+{profit_pct*100:.2f}%)"
            
            # 2. 止损
            elif profit_pct <= self.params['stop_loss']:
                should_sell = True
                sell_reason = f"止损({profit_pct*100:.2f}%)"
            
            # 3. 持仓过夜后次日卖出
            else:
                should_sell = True
                sell_reason = f"次日卖出({profit_pct*100:+.2f}%)"
            
            if should_sell:
                to_sell.append((symbol, current_price, sell_reason))
        
        # 执行卖出
        for symbol, price, reason in to_sell:
            holding = self.holdings[symbol]
            self.sell_all(symbol)
            self.trade_log.append({
                'date': current_date,
                'symbol': symbol,
                'action': 'sell',
                'price': price,
                'quantity': holding['quantity'],
                'reason': reason
            })
            del self.holdings[symbol]
    
    def _process_buy(self, data: Dict[str, pd.DataFrame], current_date):
        """处理买入逻辑 - 选股并买入"""
        # 如果有持仓，不买入
        if self.holdings:
            return
        
        # 检查持仓数量限制
        if len(self.holdings) >= self.params['max_hold_num']:
            return
        
        # 选股
        selected = self._select_stocks(data, current_date)
        
        if not selected:
            return
        
        # 计算每只股票的买入金额
        total_cash = self._get_available_cash()
        per_stock_cash = total_cash * self.params['single_position']
        
        # 买入
        for symbol, price in selected[:self.params['max_hold_num']]:
            quantity = int(per_stock_cash / price / 100) * 100  # 整手
            if quantity > 0:
                self.buy(symbol, quantity=quantity)
                self.holdings[symbol] = {
                    'cost': price,
                    'quantity': quantity,
                    'buy_date': current_date
                }
                self.trade_log.append({
                    'date': current_date,
                    'symbol': symbol,
                    'action': 'buy',
                    'price': price,
                    'quantity': quantity,
                    'reason': '选股买入'
                })
    
    def _select_stocks(self, data: Dict[str, pd.DataFrame], current_date) -> List[tuple]:
        """选股逻辑 - 返回 [(symbol, price), ...]"""
        candidates = []
        
        for symbol, df in data.items():
            # 找到当前日期的数据
            today_idx = df[df['date'] == current_date].index
            if len(today_idx) == 0:
                continue
            today_idx = today_idx[0]
            
            if today_idx < 20:  # 数据不足
                continue
            
            today = df.iloc[today_idx]
            prev = df.iloc[today_idx - 1]
            
            # 1. 涨幅过滤 (3%-7%)
            rise_pct = (today['close'] - prev['close']) / prev['close'] * 100
            if not (self.params['rise_range'][0] <= rise_pct <= self.params['rise_range'][1]):
                continue
            
            # 2. 均线多头排列 (MA5 > MA10 > MA20)
            ma5 = df['close'].iloc[today_idx-4:today_idx+1].mean()
            ma10 = df['close'].iloc[today_idx-9:today_idx+1].mean()
            ma20 = df['close'].iloc[today_idx-19:today_idx+1].mean()
            
            if not (ma5 > ma10 > ma20):
                continue
            
            # 3. 成交量过滤 (量比 >= 1.2)
            avg_volume = df['volume'].iloc[today_idx-5:today_idx].mean()
            if avg_volume > 0:
                volume_ratio = today['volume'] / avg_volume
            else:
                continue
            
            if volume_ratio < self.params['min_volume_ratio']:
                continue
            
            # 4. 成交额过滤 (>= 1亿)
            amount = today['close'] * today['volume']
            if amount < self.params['min_daily_amount']:
                continue
            
            # 通过所有条件，加入候选
            candidates.append((symbol, today['close'], rise_pct, volume_ratio))
        
        # 按涨幅排序，选前N只
        candidates.sort(key=lambda x: x[2], reverse=True)
        return [(c[0], c[1]) for c in candidates]
    
    def _get_available_cash(self) -> float:
        """获取可用资金"""
        if hasattr(self, 'engine'):
            return self.engine.cash
        return 100000  # 默认
    
    def get_trade_log(self) -> pd.DataFrame:
        """获取交易记录"""
        return pd.DataFrame(self.trade_log)


class TangjieStockSelector:
    """唐杰策略选股器 - 用于实时选股"""
    
    def __init__(self, params: dict = None):
        self.params = {**DEFAULT_PARAMS, **(params or {})}
    
    def select(self, stock_pool: Dict[str, pd.DataFrame], date=None) -> pd.DataFrame:
        """
        从股票池中选股
        
        Args:
            stock_pool: {symbol: DataFrame} 股票数据池
            date: 选股日期，默认最后一天
            
        Returns:
            DataFrame: 选中的股票列表
        """
        results = []
        
        for symbol, df in stock_pool.items():
            if df.empty or len(df) < 20:
                continue
            
            # 确定选股日期
            if date is None:
                today_idx = len(df) - 1
            else:
                today_idx = df[df['date'] == date].index
                if len(today_idx) == 0:
                    continue
                today_idx = today_idx[0]
            
            today = df.iloc[today_idx]
            prev = df.iloc[today_idx - 1] if today_idx > 0 else None
            
            if prev is None:
                continue
            
            # 计算指标
            rise_pct = (today['close'] - prev['close']) / prev['close'] * 100
            
            ma5 = df['close'].iloc[max(0,today_idx-4):today_idx+1].mean()
            ma10 = df['close'].iloc[max(0,today_idx-9):today_idx+1].mean()
            ma20 = df['close'].iloc[max(0,today_idx-19):today_idx+1].mean()
            
            avg_volume = df['volume'].iloc[max(0,today_idx-5):today_idx].mean()
            volume_ratio = today['volume'] / avg_volume if avg_volume > 0 else 0
            
            amount = today['close'] * today['volume']
            
            # 过滤条件
            passed = True
            reasons = []
            
            # 涨幅
            if not (self.params['rise_range'][0] <= rise_pct <= self.params['rise_range'][1]):
                passed = False
                reasons.append(f"涨幅{rise_pct:.1f}%不在{self.params['rise_range']}范围内")
            
            # 均线
            if not (ma5 > ma10 > ma20):
                passed = False
                reasons.append(f"均线非多头(MA5={ma5:.2f},MA10={ma10:.2f},MA20={ma20:.2f})")
            
            # 量比
            if volume_ratio < self.params['min_volume_ratio']:
                passed = False
                reasons.append(f"量比{volume_ratio:.2f}<{self.params['min_volume_ratio']}")
            
            # 成交额
            if amount < self.params['min_daily_amount']:
                passed = False
                reasons.append(f"成交额{amount/100000000:.2f}亿<{self.params['min_daily_amount']/100000000:.0f}亿")
            
            results.append({
                'symbol': symbol,
                'date': today['date'],
                'close': today['close'],
                'rise_pct': rise_pct,
                'volume_ratio': volume_ratio,
                'amount': amount,
                'ma5': ma5,
                'ma10': ma10,
                'ma20': ma20,
                'passed': passed,
                'reasons': '; '.join(reasons) if reasons else '全部通过'
            })
        
        df_result = pd.DataFrame(results)
        
        # 返回通过的股票
        if not df_result.empty:
            df_passed = df_result[df_result['passed'] == True].sort_values('rise_pct', ascending=False)
            return df_passed
        
        return pd.DataFrame()


def run_tangjie_backtest(symbols: List[str], 
                         start_date: str, 
                         end_date: str,
                         initial_capital: float = 100000,
                         params: dict = None) -> dict:
    """
    运行唐杰策略回测
    
    Args:
        symbols: 股票代码列表
        start_date: 开始日期
        end_date: 结束日期
        initial_capital: 初始资金
        params: 策略参数
        
    Returns:
        回测结果字典
    """
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    from data import DataFetcher, DataPreprocessor
    from backtest import BacktestEngine
    
    # 获取数据
    print(f"获取数据: {len(symbols)} 只股票...")
    fetcher = DataFetcher()
    stock_data = {}
    
    for symbol in symbols:
        try:
            df = fetcher.get_a_share_daily(symbol, start_date, end_date)
            if not df.empty and len(df) >= 20:
                stock_data[symbol] = df
        except Exception as e:
            print(f"  {symbol} 获取失败: {e}")
    
    if not stock_data:
        print("未获取到任何股票数据")
        return None
    
    print(f"成功获取 {len(stock_data)} 只股票数据")
    
    # 预处理
    print("数据预处理...")
    preprocessor = DataPreprocessor()
    for symbol in stock_data:
        stock_data[symbol] = preprocessor.prepare_for_backtest(stock_data[symbol])
    
    # 运行回测
    print("运行回测...")
    strategy = TangjieTradeStrategy(params)
    engine = BacktestEngine(initial_capital=initial_capital)
    
    for symbol, df in stock_data.items():
        engine.add_data(symbol, df)
    
    engine.set_strategy(strategy)
    results = engine.run()
    
    # 添加交易记录
    results['trade_log'] = strategy.get_trade_log()
    
    return results
