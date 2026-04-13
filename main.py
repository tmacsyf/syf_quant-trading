#!/usr/bin/env python3
"""量化交易系统主入口"""
import argparse
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent))

from data import DataFetcher, DataCache, DataPreprocessor
from data import RealtimeFetcher, get_realtime_quote, get_realtime_quotes
from backtest import BacktestEngine
from strategy import MovingAverageCrossStrategy, MeanReversionStrategy


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='量化交易系统')

    # 模式选择
    parser.add_argument('--realtime', '-r', action='store_true',
                       help='实时行情模式')

    parser.add_argument('--strategy', '-s', type=str, default='ma',
                       choices=['ma', 'mean_reversion'],
                       help='策略类型')

    parser.add_argument('--symbol', type=str, default='000001',
                       help='股票代码，多个用逗号分隔')

    parser.add_argument('--market', '-m', type=str, default='a_share',
                       choices=['a_share', 'hk_share', 'us_share'],
                       help='市场类型')

    parser.add_argument('--start', type=str,
                       default=(datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d'),
                       help='开始日期')

    parser.add_argument('--end', type=str,
                       default=datetime.now().strftime('%Y-%m-%d'),
                       help='结束日期')

    parser.add_argument('--capital', type=float, default=100000,
                       help='初始资金')

    return parser.parse_args()


def show_realtime(symbols: str):
    """显示实时行情"""
    codes = [s.strip() for s in symbols.split(',')]

    print("=" * 60)
    print("量化交易系统 - 实时行情")
    print("=" * 60)

    fetcher = RealtimeFetcher()
    quotes = fetcher.get_quotes(codes)

    if not quotes:
        print("未获取到行情数据")
        return

    for quote in quotes:
        fetcher.print_quote(quote)


def run_backtest(args):
    """运行回测"""
    print("=" * 60)
    print("量化交易系统 - 回测")
    print("=" * 60)
    
    print(f"\n获取数据: {args.symbol} ({args.market})...")
    fetcher = DataFetcher()
    cache = DataCache()
    
    cache_key = f"{args.market}_{args.symbol}_{args.start}_{args.end}"
    df = cache.get('stock_data', key=cache_key)
    
    if df is None:
        df = fetcher.get_stock_data(args.symbol, args.market, args.start, args.end)
        cache.set(df, 'stock_data', key=cache_key)
        print(f"  从数据源获取 {len(df)} 条数据")
    else:
        print(f"  从缓存获取 {len(df)} 条数据")
    
    print("\n数据预处理...")
    preprocessor = DataPreprocessor()
    df = preprocessor.prepare_for_backtest(df)
    print(f"  预处理后: {len(df)} 条数据")
    
    print(f"\n创建策略: {args.strategy}")
    if args.strategy == 'ma':
        strategy = MovingAverageCrossStrategy(fast_period=5, slow_period=20)
    else:
        strategy = MeanReversionStrategy(rsi_period=14, oversold=30, overbought=70)
    
    print("\n运行回测...")
    engine = BacktestEngine(initial_capital=args.capital)
    engine.add_data(args.symbol, df)
    engine.set_strategy(strategy)
    
    results = engine.run()
    
    print("\n" + "-" * 60)
    print("回测结果")
    print("-" * 60)
    
    summary = results['summary']
    print(f"初始资金:     {summary['initial_capital']:,.2f} 元")
    print(f"最终资金:     {summary['final_value']:,.2f} 元")
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


def main():
    """主函数"""
    args = parse_args()

    try:
        if args.realtime:
            show_realtime(args.symbol)
        else:
            results = run_backtest(args)
            print("\n回测完成!")
    except Exception as e:
        print(f"\n执行失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
