#!/usr/bin/env python3
"""回测演示脚本"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data import DataFetcher, DataCache, DataPreprocessor
from backtest import BacktestEngine
from strategy import MovingAverageCrossStrategy, MeanReversionStrategy


def demo_backtest():
    """回测演示"""
    print("=" * 60)
    print("量化交易系统 - 回测演示")
    print("=" * 60)
    
    # 1. 获取数据
    print("\n[1/4] 获取数据...")
    fetcher = DataFetcher()
    cache = DataCache()
    
    df = cache.get('stock_data', symbol='000001', start='2023-01-01', end='2024-01-01')
    
    if df is None:
        df = fetcher.get_a_share_daily(symbol='000001', start_date='2023-01-01', end_date='2024-01-01')
        cache.set(df, 'stock_data', symbol='000001', start='2023-01-01', end='2024-01-01')
        print(f"  从数据源获取 {len(df)} 条数据")
    else:
        print(f"  从缓存获取 {len(df)} 条数据")
    
    # 2. 数据预处理
    print("\n[2/4] 数据预处理...")
    preprocessor = DataPreprocessor()
    df = preprocessor.prepare_for_backtest(df)
    print(f"  预处理后: {len(df)} 条数据")
    
    # 3. 创建策略
    print("\n[3/4] 创建策略...")
    strategy = MovingAverageCrossStrategy(fast_period=5, slow_period=20, position_pct=0.95)
    print(f"  策略: {strategy.name}")
    
    # 4. 运行回测
    print("\n[4/4] 运行回测...")
    engine = BacktestEngine(initial_capital=100000)
    engine.add_data('000001', df)
    engine.set_strategy(strategy)
    
    results = engine.run()
    
    # 5. 输出结果
    print("\n" + "-" * 60)
    print("回测结果")
    print("-" * 60)
    
    summary = results['summary']
    print(f"初始资金:     ¥{summary['initial_capital']:,.2f}")
    print(f"最终资金:     ¥{summary['final_value']:,.2f}")
    print(f"总收益率:     {summary['total_return']*100:+.2f}%")
    print(f"年化收益率:   {summary.get('annualized_return', 0)*100:+.2f}%")
    print(f"夏普比率:     {summary.get('sharpe_ratio', 0):.2f}")
    print(f"最大回撤:     {summary.get('max_drawdown', 0)*100:.2f}%")
    print(f"交易次数:     {summary['total_trades']}")
    
    trades_df = results['trades']
    if not trades_df.empty:
        print(f"\n交易明细:")
        print(trades_df.to_string(index=False))
    
    return results


def demo_multi_strategy():
    """多策略对比"""
    print("\n" + "=" * 60)
    print("多策略对比")
    print("=" * 60)
    
    fetcher = DataFetcher()
    df = fetcher.get_a_share_daily('000001', '2023-01-01', '2024-01-01')
    
    preprocessor = DataPreprocessor()
    df = preprocessor.prepare_for_backtest(df)
    
    strategies = [
        MovingAverageCrossStrategy(fast_period=5, slow_period=20),
        MovingAverageCrossStrategy(fast_period=10, slow_period=30),
        MeanReversionStrategy(rsi_period=14, oversold=30, overbought=70),
    ]
    
    print(f"\n{'策略名称':<25} {'总收益':>10} {'年化收益':>10} {'夏普':>8} {'最大回撤':>10} {'交易次数':>8}")
    print("-" * 80)
    
    for strategy in strategies:
        engine = BacktestEngine(initial_capital=100000)
        engine.add_data('000001', df)
        engine.set_strategy(strategy)
        
        results = engine.run()
        summary = results['summary']
        
        print(f"{strategy.name:<25} "
              f"{summary['total_return']*100:>+9.2f}% "
              f"{summary.get('annualized_return', 0)*100:>+9.2f}% "
              f"{summary.get('sharpe_ratio', 0):>8.2f} "
              f"{summary.get('max_drawdown', 0)*100:>9.2f}% "
              f"{summary['total_trades']:>8}")


if __name__ == '__main__':
    demo_backtest()
    demo_multi_strategy()
    print("\n" + "=" * 60)
    print("演示完成!")
    print("=" * 60)
