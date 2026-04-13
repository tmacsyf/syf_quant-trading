"""策略基类"""
from abc import ABC, abstractmethod
from typing import Dict
import pandas as pd


class BaseStrategy(ABC):
    """策略基类"""
    
    def __init__(self, name: str = None):
        self.name = name or self.__class__.__name__
        self.params = {}
        self.is_initialized = False
    
    def set_params(self, **kwargs):
        """设置策略参数"""
        self.params.update(kwargs)
    
    def initialize(self, engine):
        """初始化策略"""
        self.engine = engine
        self.is_initialized = True
    
    @abstractmethod
    def on_data(self, data: Dict[str, pd.DataFrame]):
        """数据处理回调"""
        pass
    
    def buy(self, symbol: str, quantity: float = None, percent: float = None):
        """买入"""
        if hasattr(self, 'engine'):
            return self.engine.buy(symbol, quantity=quantity, percent=percent)
    
    def sell(self, symbol: str, quantity: float = None, percent: float = None):
        """卖出"""
        if hasattr(self, 'engine'):
            return self.engine.sell(symbol, quantity=quantity, percent=percent)
    
    def sell_all(self, symbol: str):
        """清仓"""
        if hasattr(self, 'engine'):
            return self.engine.sell_all(symbol)
    
    def get_position(self, symbol: str) -> Dict:
        """获取持仓"""
        if hasattr(self, 'engine'):
            return self.engine.get_position(symbol)
        return {}
    
    def __call__(self, engine, data: Dict[str, pd.DataFrame]):
        """使策略可调用"""
        if not self.is_initialized:
            self.initialize(engine)
        self.on_data(data)
