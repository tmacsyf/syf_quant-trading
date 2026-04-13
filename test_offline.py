#!/usr/bin/env python3
"""离线测试 - 无需网络连接"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from data import DataPreprocessor
from backtest import BacktestEngine
from strategy import MovingAverageCrossStrategy, MeanReversionStrategy


def create_mock_data(start_date='2023-01-01', end_date='2024-01-01', trend='up'):
    """
    创建模拟股票数据
    
    Args:
        trend: 'up'(上涨), 'down'(下跌), 'random'(随机)
    """
    dates = pd.date_range(start=start_date, end=end_date, freq='D')
    np.random.seed(42)
    
    price = 10
    prices = []
    
    for i in range(len(dates)):
        if trend == 'up':
            # 上涨趋势
            change = np.random.normal(0.001, 0.02)
        elif trend == 'down':
            # 下跌趋势
            change = np.random.normal(-0.001, 0.02)
        else:
            # 随机波动
            change = np.random.normal(0, 0.02)
        
        price = price * (1 + change)
        prices.append(price)
    
    df = pd.DataFrame({
        'date': dates,
        'open': prices,
        'high': [p * 1.02 for p in prices],
        'low': [p * 0.98 for p in prices],
        'close': prices,
        'volume': np.random.randint(100000, 1000000, len(dates))
    })
    
    return df


def test_strategy(strategy, df, name="策略"):
    """测试单个策略"""
    print(f"\n{'='*60}")
    print(f"测试: {name}")
    print('='*60)
    
    # 预处理
    preprocessor = DataPreprocessor()
    df_processed = preprocessor.prepare_for_backtest(df)
    print(f"数据条数: {len(df_processed)}")
    
    # 运行回测
    engine = BacktestEngine(initial_capital=100000)
    engine.add_data('TEST', df_processed)
    engine.set_strategy(strategy)
    
    results = engine.run()
    
    # 输出结果
    summary = results['summary']
    print(f"\n📊 回测结果:")
    print(f"  初始资金:     ¥{summary['initial_capital']:,.2f}")
    print(f"  最终资金:     ¥{summary['final_value']:,.2f}")
    print(f"  总收益率:     {summary['total_return']*100:+.2f}%")
    print(f"  年化收益率:   {summary.get('annualized_return', 0)*100:+.2f}%")
    print(f"  夏普比率:     {summary.get('sharpe_ratio', 0):.2f}")
    print(f"  最大回撤:     {summary.get('max_drawdown', 0)*100:.2f}%")
    print(f"  交易次数:     {summary['total_trades']}")
    
    return results


def main():
    """主函数"""
    print("="*60)
    print("量化交易系统 - 离线测试（无需网络）")
    print("="*60)
    
    # 创建不同趋势的数据
    print("\n📈 创建测试数据...")
    
    # 1. 上涨趋势
    df_up = create_mock_data(trend='up')
    
    # 2. 下跌趋势  
    df_down = create_mock_data(trend='down')
    
    # 3. 随机波动
    df_random = create_mock_data(trend='random')
    
    # 测试双均线策略
    print("\n" + "="*60)
    print("双均线策略测试")
    print("="*60)
    
    ma_strategy = MovingAverageCrossStrategy(fast_period=5, slow_period=20)
    
    test_strategy(ma_strategy, df_up, "双均线 - 上涨趋势")
    test_strategy(ma_strategy, df_down, "双均线 - 下跌趋势")
    test_strategy(ma_strategy, df_random, "双均线 - 随机波动")
    
    # 测试RSI策略
    print("\n" + "="*60)
    print("RSI均值回归策略测试")
    print("="*60)
    
    rsi_strategy = MeanReversionStrategy(rsi_period=14, oversold=30, overbought=70)
    
    test_strategy(rsi_strategy, df_up, "RSI - 上涨趋势")
    test_strategy(rsi_strategy, df_down, "RSI - 下跌趋势")
    test_strategy(rsi_strategy, df_random, "RSI - 随机波动")
    
    print("\n" + "="*60)
    print("✅ 所有测试完成！")
    print("="*60)


if __name__ == '__main__':
    main()
