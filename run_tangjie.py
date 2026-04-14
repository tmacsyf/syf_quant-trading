#!/usr/bin/env python3
"""
唐杰隔夜持股T+1策略 - 独立运行脚本

使用方法:
    python run_tangjie.py --symbols 000001,000002,600519 --start 2024-01-01 --end 2024-12-31
    python run_tangjie.py --select 50 --start 2024-01-01 --end 2024-12-31
    
参数说明:
    --symbols: 指定股票代码，逗号分隔
    --select: 自动选股数量（默认50只）
    --start: 回测开始日期
    --end: 回测结束日期
    --capital: 初始资金（默认10万）
    --list: 列出今日选股结果（不运行回测）
"""
import sys
import argparse
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from data import DataFetcher, DataPreprocessor
from backtest import BacktestEngine
from strategy import TangjieTradeStrategy, TangjieStockSelector


def get_stock_pool(count: int = 50) -> list:
    """获取股票池（这里返回一些常见的股票代码作为示例）"""
    # 实际使用时可以接入股票列表API
    common_stocks = [
        # 金融
        '000001', '600000', '600036', '601398', '601318',
        # 科技
        '000725', '002415', '002230', '000063', '600498',
        # 消费
        '600519', '000858', '600887', '002594', '000333',
        # 医药
        '600276', '000538', '600436', '300760', '603259',
        # 新能源
        '300750', '601012', '600438', '002460', '300274',
        # 半导体
        '688981', '688012', '688008', '600584', '002049',
        # 其他
        '600009', '600115', '601888', '600030', '000768',
        '002352', '600104', '601668', '601766', '600031',
        '000651', '000100', '600050', '601186', '601088',
        '600028', '601857', '600938', '601728', '600941',
        '688111', '688036', '688169', '688599', '688396',
    ]
    return common_stocks[:count]


def run_backtest(args):
    """运行回测"""
    print("=" * 70)
    print("唐杰隔夜持股T+1策略 - 回测")
    print("=" * 70)
    
    # 获取股票列表
    if args.symbols:
        symbols = [s.strip() for s in args.symbols.split(',')]
    else:
        symbols = get_stock_pool(args.select)
    
    print(f"\n股票池: {len(symbols)} 只股票")
    print(f"回测区间: {args.start} 至 {args.end}")
    print(f"初始资金: {args.capital:,.0f} 元")
    
    # 获取数据
    print("\n[1/4] 获取数据...")
    fetcher = DataFetcher()
    stock_data = {}
    
    for i, symbol in enumerate(symbols, 1):
        try:
            df = fetcher.get_a_share_daily(symbol, args.start, args.end)
            if not df.empty and len(df) >= 20:
                stock_data[symbol] = df
                print(f"  [{i}/{len(symbols)}] {symbol} - {len(df)} 条数据")
            else:
                print(f"  [{i}/{len(symbols)}] {symbol} - 数据不足，跳过")
        except Exception as e:
            print(f"  [{i}/{len(symbols)}] {symbol} - 获取失败: {e}")
    
    if not stock_data:
        print("\n错误: 未获取到任何股票数据")
        return
    
    print(f"\n成功获取 {len(stock_data)} 只股票数据")
    
    # 预处理
    print("\n[2/4] 数据预处理...")
    preprocessor = DataPreprocessor()
    for symbol in stock_data:
        stock_data[symbol] = preprocessor.prepare_for_backtest(stock_data[symbol])
    
    # 创建策略
    print("\n[3/4] 创建策略...")
    params = {
        'rise_range': (args.min_rise, args.max_rise),
        'min_volume_ratio': args.min_volume_ratio,
        'min_daily_amount': args.min_amount,
        'take_profit': args.take_profit,
        'stop_loss': args.stop_loss,
        'max_hold_num': args.max_hold,
        'single_position': args.position,
    }
    strategy = TangjieTradeStrategy(params)
    print(f"  选股条件: 涨幅 {args.min_rise}%-{args.max_rise}%, 量比≥{args.min_volume_ratio}")
    print(f"  止盈止损: +{args.take_profit*100:.0f}% / {args.stop_loss*100:.0f}%")
    print(f"  仓位控制: 单票{args.position*100:.0f}%, 最多{args.max_hold}只")
    
    # 运行回测
    print("\n[4/4] 运行回测...")
    engine = BacktestEngine(initial_capital=args.capital)
    
    for symbol, df in stock_data.items():
        engine.add_data(symbol, df)
    
    engine.set_strategy(strategy)
    results = engine.run()
    
    # 输出结果
    print("\n" + "=" * 70)
    print("回测结果")
    print("=" * 70)
    
    summary = results['summary']
    print(f"\n初始资金:     {summary['initial_capital']:,.2f} 元")
    print(f"最终资金:     {summary['final_value']:,.2f} 元")
    print(f"总收益率:     {summary['total_return']*100:+.2f}%")
    print(f"年化收益率:   {summary.get('annualized_return', 0)*100:+.2f}%")
    print(f"夏普比率:     {summary.get('sharpe_ratio', 0):.2f}")
    print(f"最大回撤:     {summary.get('max_drawdown', 0)*100:.2f}%")
    print(f"交易次数:     {summary['total_trades']}")
    
    # 交易记录
    trade_log = strategy.get_trade_log()
    if not trade_log.empty:
        print(f"\n交易明细 ({len(trade_log)} 笔):")
        print(trade_log.to_string(index=False))
        
        # 统计
        buy_count = len(trade_log[trade_log['action'] == 'buy'])
        sell_count = len(trade_log[trade_log['action'] == 'sell'])
        print(f"\n买入次数: {buy_count}, 卖出次数: {sell_count}")
    
    print("\n" + "=" * 70)
    print("回测完成!")
    print("=" * 70)
    
    return results


def run_select(args):
    """运行选股"""
    print("=" * 70)
    print("唐杰隔夜持股T+1策略 - 今日选股")
    print("=" * 70)
    
    # 获取股票池
    symbols = get_stock_pool(args.select)
    print(f"\n股票池: {len(symbols)} 只股票")
    
    # 获取数据
    print("\n获取数据...")
    fetcher = DataFetcher()
    stock_data = {}
    
    # 获取最近60天数据
    end_date = datetime.now().strftime('%Y%m%d')
    start_date = (datetime.now() - timedelta(days=60)).strftime('%Y%m%d')
    
    for symbol in symbols:
        try:
            df = fetcher.get_a_share_daily(symbol, start_date, end_date)
            if not df.empty and len(df) >= 20:
                stock_data[symbol] = df
        except Exception as e:
            pass
    
    print(f"成功获取 {len(stock_data)} 只股票数据")
    
    # 选股
    print("\n执行选股...")
    selector = TangjieStockSelector({
        'rise_range': (args.min_rise, args.max_rise),
        'min_volume_ratio': args.min_volume_ratio,
        'min_daily_amount': args.min_amount,
    })
    
    selected = selector.select(stock_data)
    
    if selected.empty:
        print("\n今日无符合选股条件的股票")
    else:
        print(f"\n选中 {len(selected)} 只股票:")
        print("-" * 70)
        display_cols = ['symbol', 'date', 'close', 'rise_pct', 'volume_ratio', 'amount', 'reasons']
        for col in display_cols:
            if col not in selected.columns:
                selected[col] = ''
        
        # 格式化输出
        for idx, row in selected.iterrows():
            print(f"\n【{row['symbol']}】")
            print(f"  日期: {row['date']}")
            print(f"  收盘价: {row['close']:.2f} 元")
            print(f"  涨幅: {row['rise_pct']:.2f}%")
            print(f"  量比: {row['volume_ratio']:.2f}")
            print(f"  成交额: {row['amount']/100000000:.2f} 亿元")
            print(f"  均线: MA5={row['ma5']:.2f}, MA10={row['ma10']:.2f}, MA20={row['ma20']:.2f}")
        
        print("\n" + "-" * 70)
        print(f"建议关注前 {args.max_hold} 只:")
        for i, (idx, row) in enumerate(selected.head(args.max_hold).iterrows(), 1):
            print(f"  {i}. {row['symbol']} - 涨幅{row['rise_pct']:.2f}%")
    
    print("\n" + "=" * 70)
    print("选股完成!")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description='唐杰隔夜持股T+1策略',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 运行回测（指定股票）
  python run_tangjie.py --symbols 000001,000002,600519 --start 2024-01-01 --end 2024-12-31
  
  # 运行回测（自动选股50只）
  python run_tangjie.py --select 50 --start 2024-01-01 --end 2024-12-31
  
  # 今日选股（不运行回测）
  python run_tangjie.py --list --select 100
        """
    )
    
    # 模式选择
    parser.add_argument('--list', action='store_true',
                       help='仅选股，不运行回测')
    
    # 股票池
    parser.add_argument('--symbols', type=str,
                       help='指定股票代码，逗号分隔，如：000001,000002,600519')
    parser.add_argument('--select', type=int, default=50,
                       help='自动选股数量（默认50只）')
    
    # 回测参数
    parser.add_argument('--start', type=str,
                       default=(datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d'),
                       help='回测开始日期（默认一年前）')
    parser.add_argument('--end', type=str,
                       default=datetime.now().strftime('%Y-%m-%d'),
                       help='回测结束日期（默认今天）')
    parser.add_argument('--capital', type=float, default=100000,
                       help='初始资金（默认10万）')
    
    # 策略参数
    parser.add_argument('--min-rise', type=float, default=3,
                       help='最小涨幅（默认3%）')
    parser.add_argument('--max-rise', type=float, default=7,
                       help='最大涨幅（默认7%）')
    parser.add_argument('--min-volume-ratio', type=float, default=1.2,
                       help='最小量比（默认1.2）')
    parser.add_argument('--min-amount', type=float, default=100000000,
                       help='最小成交额（默认1亿）')
    parser.add_argument('--take-profit', type=float, default=0.03,
                       help='止盈比例（默认3%）')
    parser.add_argument('--stop-loss', type=float, default=-0.02,
                       help='止损比例（默认-2%）')
    parser.add_argument('--max-hold', type=int, default=5,
                       help='最大持仓数（默认5只）')
    parser.add_argument('--position', type=float, default=0.1,
                       help='单票仓位（默认10%）')
    
    args = parser.parse_args()
    
    try:
        if args.list:
            run_select(args)
        else:
            run_backtest(args)
    except KeyboardInterrupt:
        print("\n\n用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
