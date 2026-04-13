"""数据预处理模块"""
import pandas as pd
import numpy as np


class DataPreprocessor:
    """数据预处理器"""
    
    @staticmethod
    def clean_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
        """清洗OHLCV数据"""
        df = df.copy()
        
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"缺少必要列: {col}")
        
        # 去除价格为0或负数的行
        price_cols = ['open', 'high', 'low', 'close']
        for col in price_cols:
            df = df[df[col] > 0]
        
        # 确保价格逻辑正确
        df['high'] = df[['open', 'high', 'low', 'close']].max(axis=1)
        df['low'] = df[['open', 'high', 'low', 'close']].min(axis=1)
        
        df = df.dropna(subset=price_cols)
        df['volume'] = df['volume'].clip(lower=0)
        
        return df.reset_index(drop=True)
    
    @staticmethod
    def add_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """添加常用技术指标"""
        df = df.copy()
        
        # 价格变化
        df['returns'] = df['close'].pct_change()
        
        # 移动平均线
        for period in [5, 10, 20, 60]:
            df[f'ma_{period}'] = df['close'].rolling(window=period).mean()
        
        # 指数移动平均线
        df['ema_12'] = df['close'].ewm(span=12, adjust=False).mean()
        df['ema_26'] = df['close'].ewm(span=26, adjust=False).mean()
        
        # MACD
        df['macd'] = df['ema_12'] - df['ema_26']
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # 布林带
        df['bb_middle'] = df['close'].rolling(window=20).mean()
        bb_std = df['close'].rolling(window=20).std()
        df['bb_upper'] = df['bb_middle'] + (bb_std * 2)
        df['bb_lower'] = df['bb_middle'] - (bb_std * 2)
        
        # ATR
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        df['atr'] = true_range.rolling(14).mean()
        
        # 波动率
        df['volatility_20'] = df['returns'].rolling(window=20).std() * np.sqrt(252)
        
        return df
    
    @staticmethod
    def prepare_for_backtest(df: pd.DataFrame) -> pd.DataFrame:
        """准备回测数据"""
        df = DataPreprocessor.clean_ohlcv(df)
        df = DataPreprocessor.add_technical_indicators(df)
        # 只删除价格相关的NaN，保留技术指标列
        price_cols = ['open', 'high', 'low', 'close', 'volume']
        df = df.dropna(subset=price_cols)
        return df.reset_index(drop=True)
