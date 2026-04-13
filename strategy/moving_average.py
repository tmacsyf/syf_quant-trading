"""双均线交叉策略"""
import pandas as pd
from typing import Dict

from .base import BaseStrategy


class MovingAverageCrossStrategy(BaseStrategy):
    """双均线交叉策略 - 金叉买入，死叉卖出"""
    
    def __init__(self, fast_period: int = 5, slow_period: int = 20, position_pct: float = 0.95):
        super().__init__("MovingAverageCross")
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.position_pct = position_pct
    
    def on_data(self, data: Dict[str, pd.DataFrame]):
        """处理数据"""
        for symbol, df in data.items():
            if len(df) < self.slow_period + 1:
                continue
            
            # 计算均线 (使用copy避免警告)
            df = df.copy()
            df['ma_fast'] = df['close'].rolling(window=self.fast_period).mean()
            df['ma_slow'] = df['close'].rolling(window=self.slow_period).mean()
            
            current_fast = df['ma_fast'].iloc[-1]
            current_slow = df['ma_slow'].iloc[-1]
            prev_fast = df['ma_fast'].iloc[-2]
            prev_slow = df['ma_slow'].iloc[-2]
            
            if pd.isna(current_fast) or pd.isna(current_slow):
                continue
            
            # 判断交叉
            current_status = current_fast > current_slow
            prev_status = prev_fast > prev_slow
            
            position = self.get_position(symbol)
            has_position = position.get('quantity', 0) > 0
            
            # 金叉买入
            if not prev_status and current_status and not has_position:
                self.buy(symbol, percent=self.position_pct)
            
            # 死叉卖出
            elif prev_status and not current_status and has_position:
                self.sell_all(symbol)


class MeanReversionStrategy(BaseStrategy):
    """RSI均值回归策略 - 超卖买入，超买卖出"""
    
    def __init__(self, rsi_period: int = 14, oversold: int = 30, overbought: int = 70, position_pct: float = 0.9):
        super().__init__("MeanReversion")
        self.rsi_period = rsi_period
        self.oversold = oversold
        self.overbought = overbought
        self.position_pct = position_pct
    
    def on_data(self, data: Dict[str, pd.DataFrame]):
        """处理数据"""
        for symbol, df in data.items():
            if len(df) < self.rsi_period + 5 or 'rsi' not in df.columns:
                continue
            
            current_rsi = df['rsi'].iloc[-1]
            
            if pd.isna(current_rsi):
                continue
            
            position = self.get_position(symbol)
            has_position = position.get('quantity', 0) > 0
            
            # RSI超卖买入
            if not has_position and current_rsi < self.oversold:
                self.buy(symbol, percent=self.position_pct)
            
            # RSI超买卖出
            elif has_position and current_rsi > self.overbought:
                self.sell_all(symbol)
