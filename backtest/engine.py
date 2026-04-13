"""回测引擎"""
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Callable


class BacktestEngine:
    """事件驱动回测引擎"""
    
    def __init__(self, initial_capital: float = 100000):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions: Dict[str, float] = {}
        self.position_cost: Dict[str, float] = {}
        
        self.data: Dict[str, pd.DataFrame] = {}
        self.current_date: Optional[datetime] = None
        self.current_prices: Dict[str, float] = {}
        
        self.trades: List[Dict] = []
        self.daily_values: List[Dict] = []
        
        self.strategy: Optional[Callable] = None
    
    def add_data(self, symbol: str, df: pd.DataFrame):
        """添加股票数据"""
        required_cols = ['date', 'open', 'high', 'low', 'close', 'volume']
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"数据缺少必要列: {col}")
        
        df = df.copy()
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)
        self.data[symbol] = df
    
    def set_strategy(self, strategy: Callable):
        """设置策略"""
        self.strategy = strategy
    
    def run(self, start_date: str = None, end_date: str = None) -> Dict:
        """运行回测"""
        if not self.data:
            raise ValueError("请先添加数据")
        
        # 确定回测日期范围
        all_dates = set()
        for df in self.data.values():
            all_dates.update(df['date'].tolist())
        dates = sorted(all_dates)
        
        if start_date:
            start_date = pd.to_datetime(start_date)
            dates = [d for d in dates if d >= start_date]
        
        if end_date:
            end_date = pd.to_datetime(end_date)
            dates = [d for d in dates if d <= end_date]
        
        # 遍历每个交易日
        for date in dates:
            self.current_date = date
            self._update_prices(date)
            self._update_portfolio_value()
            self._execute_strategy()
        
        return self.get_results()
    
    def _update_prices(self, date: datetime):
        """更新当前价格"""
        self.current_prices = {}
        for symbol, df in self.data.items():
            day_data = df[df['date'] == date]
            if not day_data.empty:
                self.current_prices[symbol] = day_data['close'].values[0]
    
    def _update_portfolio_value(self):
        """更新组合市值"""
        positions_value = 0
        for symbol, qty in self.positions.items():
            if symbol in self.current_prices:
                positions_value += qty * self.current_prices[symbol]
        
        total_value = self.cash + positions_value
        
        self.daily_values.append({
            'timestamp': self.current_date,
            'total_value': total_value,
            'cash': self.cash,
            'positions_value': positions_value
        })
    
    def _execute_strategy(self):
        """执行策略"""
        current_data = {}
        for symbol, df in self.data.items():
            hist_data = df[df['date'] <= self.current_date]
            if not hist_data.empty:
                current_data[symbol] = hist_data
        
        if self.strategy:
            try:
                self.strategy(self, current_data)
            except Exception as e:
                print(f"策略执行错误: {e}")
    
    def buy(self, symbol: str, quantity: float = None, percent: float = None):
        """买入"""
        if symbol not in self.current_prices:
            return None
        
        price = self.current_prices[symbol]
        
        if quantity is None and percent is not None:
            cash_to_use = self.cash * percent
            quantity = int(cash_to_use / price)
        
        if quantity is None or quantity <= 0:
            return None
        
        cost = quantity * price
        commission = cost * 0.0003  # 万3手续费
        
        if cost + commission > self.cash:
            return None
        
        # 更新持仓
        if symbol in self.positions:
            total_cost = self.positions[symbol] * self.position_cost.get(symbol, price) + cost
            self.positions[symbol] += quantity
            self.position_cost[symbol] = total_cost / self.positions[symbol]
        else:
            self.positions[symbol] = quantity
            self.position_cost[symbol] = price
        
        self.cash -= (cost + commission)
        
        # 记录交易
        self.trades.append({
            'timestamp': self.current_date,
            'symbol': symbol,
            'side': 'buy',
            'quantity': quantity,
            'price': price,
            'commission': commission,
            'amount': cost
        })
        
        return True
    
    def sell(self, symbol: str, quantity: float = None, percent: float = None):
        """卖出"""
        if symbol not in self.current_prices or symbol not in self.positions:
            return None
        
        price = self.current_prices[symbol]
        
        if quantity is None and percent is not None:
            quantity = self.positions[symbol] * percent
        
        if quantity is None or quantity <= 0 or quantity > self.positions[symbol]:
            return None
        
        revenue = quantity * price
        commission = revenue * 0.0003
        
        # 更新持仓
        self.positions[symbol] -= quantity
        if self.positions[symbol] == 0:
            del self.positions[symbol]
            del self.position_cost[symbol]
        
        self.cash += (revenue - commission)
        
        # 记录交易
        self.trades.append({
            'timestamp': self.current_date,
            'symbol': symbol,
            'side': 'sell',
            'quantity': quantity,
            'price': price,
            'commission': commission,
            'amount': revenue
        })
        
        return True
    
    def sell_all(self, symbol: str):
        """清仓"""
        if symbol in self.positions:
            return self.sell(symbol, quantity=self.positions[symbol])
        return None
    
    def get_position(self, symbol: str) -> Dict:
        """获取持仓信息"""
        qty = self.positions.get(symbol, 0)
        cost = self.position_cost.get(symbol, 0)
        price = self.current_prices.get(symbol, cost)
        
        return {
            'symbol': symbol,
            'quantity': qty,
            'avg_cost': cost,
            'market_value': qty * price,
            'unrealized_pnl': qty * (price - cost) if qty > 0 else 0
        }
    
    def get_results(self) -> Dict:
        """获取回测结果"""
        equity_df = pd.DataFrame(self.daily_values) if self.daily_values else pd.DataFrame()
        trades_df = pd.DataFrame(self.trades) if self.trades else pd.DataFrame()
        
        final_value = self.daily_values[-1]['total_value'] if self.daily_values else self.initial_capital
        total_return = (final_value - self.initial_capital) / self.initial_capital
        
        summary = {
            'initial_capital': self.initial_capital,
            'final_value': final_value,
            'total_return': total_return,
            'total_trades': len(trades_df),
            'cash': self.cash
        }
        
        if not equity_df.empty and len(equity_df) > 1:
            equity_df['returns'] = equity_df['total_value'].pct_change()
            summary['sharpe_ratio'] = self._calculate_sharpe(equity_df['returns'])
            summary['max_drawdown'] = self._calculate_max_drawdown(equity_df['total_value'])
            summary['annualized_return'] = self._calculate_annualized_return(total_return, len(equity_df))
        
        return {
            'summary': summary,
            'equity_curve': equity_df,
            'trades': trades_df
        }
    
    def _calculate_sharpe(self, returns: pd.Series, risk_free_rate: float = 0.02) -> float:
        """计算夏普比率"""
        if returns.std() == 0:
            return 0
        excess_returns = returns.mean() * 252 - risk_free_rate
        return excess_returns / (returns.std() * np.sqrt(252))
    
    def _calculate_max_drawdown(self, values: pd.Series) -> float:
        """计算最大回撤"""
        peak = values.expanding().max()
        drawdown = (values - peak) / peak
        return drawdown.min()
    
    def _calculate_annualized_return(self, total_return: float, n_days: int) -> float:
        """计算年化收益率"""
        if n_days == 0:
            return 0
        years = n_days / 252
        return (1 + total_return) ** (1 / years) - 1