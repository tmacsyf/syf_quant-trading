#!/usr/bin/env python3
"""唐杰策略 - 科创板实时选股
用实时行情筛选涨幅，再用历史数据验证均线和量比
"""
import sys
import io
import time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from data.realtime import RealtimeFetcher
from data import DataFetcher


def get_kcb_symbols():
    """获取科创板全部股票代码"""
    try:
        df = ak.stock_info_sh_name_code(symbol='科创板')
        return sorted(df['证券代码'].tolist())
    except Exception as e:
        print('获取科创板股票列表失败: {}'.format(e))
        return []


def fetch_realtime_batch(fetcher, symbols, batch_size=80):
    """分批获取实时行情"""
    all_quotes = []
    total = len(symbols)
    for i in range(0, total, batch_size):
        batch = symbols[i:i+batch_size]
        quotes = fetcher.get_quotes(batch)
        all_quotes.extend(quotes)
        if (i // batch_size + 1) % 3 == 0:
            print('  实时行情: {}/{}'.format(min(i+batch_size, total), total))
    return all_quotes


def calc_technical_with_realtime(symbol, historical_df, realtime_quote):
    """
    用历史数据+实时行情计算技术指标
    将今日实时数据追加到历史数据末尾，再计算均线和量比
    """
    today_row = pd.DataFrame([{
        'date': pd.Timestamp(datetime.now().date()),
        'open': realtime_quote.open,
        'high': realtime_quote.high,
        'low': realtime_quote.low,
        'close': realtime_quote.price,
        'volume': float(realtime_quote.volume),
        'amount': float(realtime_quote.amount),
    }])

    df = pd.concat([historical_df, today_row], ignore_index=True)
    df = df.sort_values('date').reset_index(drop=True)

    today_idx = len(df) - 1
    today = df.iloc[today_idx]

    rise_pct = realtime_quote.change_pct

    ma5 = df['close'].iloc[max(0, today_idx-4):today_idx+1].mean()
    ma10 = df['close'].iloc[max(0, today_idx-9):today_idx+1].mean()
    ma20 = df['close'].iloc[max(0, today_idx-19):today_idx+1].mean()

    avg_volume = df['volume'].iloc[max(0, today_idx-5):today_idx].mean()
    volume_ratio = today['volume'] / avg_volume if avg_volume > 0 else 0

    amount = realtime_quote.amount

    return {
        'symbol': symbol,
        'name': realtime_quote.name,
        'close': realtime_quote.price,
        'rise_pct': rise_pct,
        'volume_ratio': round(volume_ratio, 2),
        'amount': amount,
        'amount_yi': round(amount / 100000000, 2),
        'ma5': round(ma5, 2),
        'ma10': round(ma10, 2),
        'ma20': round(ma20, 2),
        'ma_bullish': ma5 > ma10 > ma20,
        'industry': '待查',
    }


def batch_get_industry(symbols):
    """批量获取行业信息，优先API，失败则用本地映射"""
    industry_map = {}
    # 先尝试API获取
    for i, symbol in enumerate(symbols):
        try:
            info = ak.stock_individual_info_em(symbol=symbol)
            industry = info[info['item'] == '行业']['value'].values
            industry_map[symbol] = industry[0] if len(industry) > 0 else None
        except Exception:
            industry_map[symbol] = None
        if (i + 1) % 3 == 0 and i < len(symbols) - 1:
            time.sleep(0.5)

    # API获取失败的，用本地映射补充
    missing = [s for s, v in industry_map.items() if v is None]
    if missing:
        local_map = get_local_industry_map()
        for s in missing:
            industry_map[s] = local_map.get(s, '其他')
    return industry_map


def get_local_industry_map():
    """本地科创板行业映射表（基于东方财富行业分类）"""
    return {
        # 半导体/芯片
        '688981': '半导体/芯片',  # 中芯国际
        '688012': '半导体/芯片',  # 中微公司
        '688008': '半导体/芯片',  # 澜起科技
        '688396': '半导体/芯片',  # 华润微
        '688019': '半导体/芯片',  # 安集科技
        '688072': '半导体/芯片',  # 拓荆科技
        '688082': '半导体/芯片',  # 盛美上海
        '688220': '半导体/芯片',  # 翱捷科技
        '688153': '半导体/芯片',  # 唯捷创芯
        '688409': '半导体/芯片',  # 富创精密
        '688234': '半导体/芯片',  # 天岳先进
        '688268': '半导体/芯片',  # 华特气体
        '688172': '半导体/芯片',  # 燕东微
        '688342': '半导体/芯片',  # 时代电气
        '688256': 'AI/芯片',      # 寒武纪
        '688041': '半导体/芯片',  # 海光信息
        '688049': '半导体/芯片',  # 炬芯科技
        '688120': '半导体/芯片',  # 华峰测控... 不对这是688200
        '688200': '半导体/芯片',  # 华峰测控
        '688005': '新能源/电池材料',  # 容百科技
        '688116': '新能源/电池材料',  # 天奈科技
        '688006': '新能源/锂电',  # 杭可科技
        '688778': '新能源/电池材料',  # 厦钨新能
        '688223': '新能源/光伏',  # 晶科能源
        '688599': '新能源/光伏',  # 天合光能
        '688339': '新能源/氢能',  # 亿华通
        '688036': '消费电子',     # 传音控股
        '688111': 'AI/软件',      # 金山办公
        '688169': '消费电子/家电',  # 石头科技
        '688561': 'AI/安全',      # 奇安信
        '688009': '轨交设备',     # 中国通号
        '688185': '生物医药',     # 康希诺
        '688180': '生物医药',     # 君实生物
        '688276': '生物医药',     # 百克生物
        '688520': '生物医药',     # 神州细胞
        '688266': '生物医药',     # 泽璟制药
        '688382': '生物医药',     # 益方生物
        '688062': '生物医药',     # 迈威生物
        '688188': '高端制造',     # 柏楚电子
        '688301': '高端制造',     # 奕瑞科技
        '688686': '高端制造',     # 奥普特
        '688017': '高端制造',     # 绿的谐波
        '688122': '新材料',       # 西部超导
        '688295': '新材料',       # 中复神鹰
        '688787': 'AI/数据',      # 海天瑞声
        '688327': 'AI/软件',      # 云从科技
        '688207': 'AI/视觉',      # 格灵深瞳
        '688292': 'AI/通信',      # 浩瀚深度
        '688628': '高端制造/仪器仪表',  # 优利德
        '688661': '半导体/芯片',  # 和林微纳
        '688143': '通信/光纤',    # 长盈通
        '688530': '半导体/芯片',  # 欧莱新材
        '688069': '环保',        # 德林海
        '688551': '高端制造',     # 科威尔
        '688229': 'AI/软件',      # 博睿数据
        '688288': '汽车/智能驾驶',  # 鸿泉技术
        '688648': '高端制造',     # 中邮科技
        '688020': '半导体/芯片',  # 方邦股份
        '688226': '新能源/电气',  # 威腾电气
        '688678': '半导体/芯片',  # 福立旺
        '688279': '半导体/芯片',  # 峰岹科技
        '688138': '光学/光电',    # 清溢光电
        '688253': '生物医药',     # 英诺特
        '688001': '半导体/芯片',  # 华兴源创
        '688252': '半导体/芯片',  # 天德钰
        '688362': '半导体/芯片',  # 甬矽电子
        '688809': '半导体/芯片',  # 强一股份
        '688511': '军工/光电',    # 天微电子
        '688028': '高端制造',     # 沃尔德
        '688307': '光学/光电',    # 中润光学
        '688521': '半导体/芯片',  # 芯原股份
        '688335': '环保',        # 复洁科技
        '688313': '通信/光通信',  # 仕佳光子
        '688558': '高端制造',     # 国盛智科
        '688115': '高端制造',     # 思林杰
        '688619': 'AI/软件',      # 罗普特
        '688381': '半导体/芯片',  # 帝奥微
        '688508': '半导体/芯片',  # 芯朋微
        '688141': '半导体/芯片',  # 杰华特
        '688552': '军工/航天',    # 航天南湖
        '688719': '高端制造',     # 爱科赛博
        '688676': '新能源/电气',  # 金盘科技
        '688597': '高端制造',     # 煜邦电力
        '688123': '半导体/芯片',  # 聚辰股份
        '688258': 'AI/软件',      # 卓易信息
        '688233': '半导体/芯片',  # 神工股份
        '688328': '高端制造',     # 深科达
        '688807': '通信/光通信',  # 优迅股份
        '688330': '高端制造',     # 宏力达
        '688498': '半导体/芯片',  # 源杰科技
        '688398': '新材料',       # 赛特新材
        '688316': 'AI/软件',      # 青云科技
        '688168': 'AI/安全',      # 安博通
        '688515': '半导体/芯片',  # 裕太微
        '688367': '高端制造',     # 工大高科
        '688798': '半导体/芯片',  # 艾为电子
        '688218': '高端制造',     # 江苏北人
        '688249': '半导体/芯片',  # 晶合集成
        '688181': '半导体/芯片',  # 八亿时空
        '688720': '半导体/芯片',  # 艾森股份
        '688378': '光学/光电',    # 奥来德
        '688380': '半导体/芯片',  # 中微半导
        '688609': '通信/5G',      # 九联科技
        '688721': '半导体/芯片',  # 龙图光罩
        '688469': '半导体/芯片',  # 芯联集成
        '688283': '高端制造',     # 坤恒顺维
        '688008': '半导体/芯片',  # 澜起科技
        '688361': '半导体/芯片',  # 中科飞测
        '688352': '半导体/芯片',  # 颀中科技
        '688012': '半导体/芯片',  # 中微公司
        '688037': '半导体/芯片',  # 芯源微
        '688158': 'AI/云计算',    # 优刻得
    }


# ========== 主流程 ==========
print('=' * 70)
print('唐杰策略 - 科创板实时选股')
print('日期: {}'.format(datetime.now().strftime('%Y-%m-%d %H:%M')))
print('=' * 70)

print('\n【策略参数】')
print('  涨幅条件: 7% ~ 19.5%（排除涨停，科创板涨停20%）')
print('  量比: >= 1.2')
print('  均线: MA5 > MA10 > MA20')
print('  成交额: >= 1亿')
print('  排除: 涨停股（涨幅>=19.5%无法买入）')

# [1/3] 获取科创板股票列表
print('\n[1/3] 获取科创板股票列表...')
symbols = get_kcb_symbols()
if not symbols:
    print('获取失败，退出')
    sys.exit(1)
print('  科创板共 {} 只股票'.format(len(symbols)))

# [2/3] 获取实时行情，筛选涨幅>3%的
print('\n[2/3] 获取实时行情...')
fetcher = RealtimeFetcher()
quotes = fetch_realtime_batch(fetcher, symbols)
print('  获取到 {} 只实时行情'.format(len(quotes)))

KCB_LIMIT_UP = 19.5
candidates = []
for q in quotes:
    if q.price <= 0:
        continue
    if q.change_pct > 3 and q.change_pct < KCB_LIMIT_UP:
        candidates.append(q)

candidates.sort(key=lambda x: x.change_pct, reverse=True)
print('  涨幅3%~{:.1f}%的候选股: {} 只（排除涨停）'.format(KCB_LIMIT_UP, len(candidates)))

if not candidates:
    print('\n今日科创板无涨幅超过3%的股票，无选股结果。')
    print('免责声明: 本选股结果仅供学习研究，不构成投资建议。')
    sys.exit(0)

print('\n  涨幅前10:')
for q in candidates[:10]:
    print('    {} {} +{:.2f}% 成交额{:.2f}亿'.format(
        q.code, q.name, q.change_pct, q.amount/100000000))

# [3/4] 获取候选股历史数据，验证均线和量比（不查行业，提速）
print('\n[3/4] 获取候选股历史数据，验证技术指标...')
data_fetcher = DataFetcher()
end_date = datetime.now().strftime('%Y%m%d')
start_date = (datetime.now() - timedelta(days=90)).strftime('%Y%m%d')

results = []
for i, q in enumerate(candidates, 1):
    try:
        df = data_fetcher.get_a_share_daily(q.code, start_date, end_date)
        if df.empty or len(df) < 20:
            continue
        result = calc_technical_with_realtime(q.code, df, q)
        results.append(result)
        print('  [{}/{}] {} {} +{:.2f}% 量比{:.2f} 均线{} 成交额{:.2f}亿'.format(
            i, len(candidates), q.code, q.name, q.change_pct,
            result['volume_ratio'],
            '多头' if result['ma_bullish'] else '非多头',
            result['amount_yi']))
    except Exception:
        pass

# ========== 筛选结果 ==========
passed = [r for r in results if 7 < r['rise_pct'] < KCB_LIMIT_UP
          and r['volume_ratio'] >= 1.2
          and r['ma_bullish'] and r['amount'] >= 100000000]

partial = [r for r in results if 7 < r['rise_pct'] < KCB_LIMIT_UP and r not in passed]

limit_up = [r for r in results if r['rise_pct'] >= KCB_LIMIT_UP]

classic = [r for r in results if 3 < r['rise_pct'] <= 7 and r['ma_bullish']
           and r['volume_ratio'] >= 1.2 and r['amount'] >= 100000000]

# [4/4] 只对选中的股票查行业（数量少，不会被限流）
selected_all = passed + partial + limit_up + classic
if selected_all:
    selected_codes = list(set(r['symbol'] for r in selected_all))
    print('\n[4/4] 获取 {} 只选中股票的行业信息...'.format(len(selected_codes)))
    industry_map = batch_get_industry(selected_codes)
    # 分类映射（直接使用行业信息，不再二次归类）
    for r in selected_all:
        r['industry'] = industry_map.get(r['symbol'], '其他')
    print('  行业信息获取完成')
else:
    print('\n[4/4] 无选中股票，跳过行业查询')

# ========== 辅助函数 ==========
def print_stock_detail(r, rank=None):
    """打印单只股票完整信息"""
    prefix = '  {}. '.format(rank) if rank else '  '
    ma_status = '多头' if r['ma_bullish'] else '非多头'
    above_ma5 = (r['close'] - r['ma5']) / r['ma5'] * 100
    price = r['close']
    quantity = int(100000 / price / 100) * 100
    actual = quantity * price

    print('{}{} {} [{}]'.format(prefix, r['symbol'], r['name'], r['industry']))
    print('     现价: {:.2f}  涨幅: {:.2f}%  成交额: {:.2f}亿'.format(
        r['close'], r['rise_pct'], r['amount_yi']))
    print('     量比: {:.2f}  均线: {}(MA5={:.2f} > MA10={:.2f} > MA20={:.2f})'.format(
        r['volume_ratio'], ma_status, r['ma5'], r['ma10'], r['ma20']))
    print('     高于MA5: {:.2f}%  建议买入: {}股 @ {:.2f}元 = {:.2f}万元'.format(
        above_ma5, quantity, price, actual/10000))


def save_to_csv(all_results, filepath):
    """保存所有结果到CSV"""
    rows = []
    for r in all_results:
        price = r['close']
        quantity = int(100000 / price / 100) * 100
        actual = quantity * price
        rows.append({
            '股票代码': r['symbol'],
            '股票名称': r['name'],
            '板块': r['industry'],
            '现价': round(r['close'], 2),
            '涨幅%': round(r['rise_pct'], 2),
            '量比': r['volume_ratio'],
            '成交额(亿)': r['amount_yi'],
            'MA5': r['ma5'],
            'MA10': r['ma10'],
            'MA20': r['ma20'],
            '均线多头': '是' if r['ma_bullish'] else '否',
            '高于MA5%': round((r['close'] - r['ma5']) / r['ma5'] * 100, 2),
            '买入股数': quantity,
            '买入金额(万)': round(actual/10000, 2),
            '筛选结果': r.get('filter_result', ''),
        })
    df = pd.DataFrame(rows)
    df.to_csv(filepath, index=False, encoding='utf-8-sig')
    return filepath


# ========== 输出结果 ==========
print('\n' + '=' * 80)
print('选股结果')
print('=' * 80)

if passed:
    print('\n*** 完全满足条件（涨幅7%-19.5%+量比>=1.2+均线多头+成交额>=1亿）*** {}只'.format(len(passed)))
    print('-' * 80)
    for i, r in enumerate(passed, 1):
        print_stock_detail(r, rank=i)
        print()
else:
    print('\n今日无完全满足条件的科创板股票（涨幅7%-19.5%+量比>=1.2+均线多头+成交额>=1亿）')

if limit_up:
    print('\n涨停股（涨幅>=19.5%，无法买入，仅供参考）{}只:'.format(len(limit_up)))
    print('-' * 80)
    for i, r in enumerate(limit_up, 1):
        print_stock_detail(r, rank=i)
        print()

if partial:
    print('\n涨幅>7%但其他条件不完全满足 {}只:'.format(len(partial)))
    print('-' * 80)
    for i, r in enumerate(partial, 1):
        issues = []
        if r['volume_ratio'] < 1.2:
            issues.append('量比{:.2f}<1.2'.format(r['volume_ratio']))
        if not r['ma_bullish']:
            issues.append('均线非多头')
        if r['amount'] < 100000000:
            issues.append('成交额{:.2f}亿<1亿'.format(r['amount_yi']))
        print_stock_detail(r, rank=i)
        print('     不满足: {}'.format(', '.join(issues)))
        print()

if classic:
    print('\n原版策略范围（涨幅3%-7%+量比>=1.2+均线多头+成交额>=1亿）{}只:'.format(len(classic)))
    print('-' * 80)
    for i, r in enumerate(classic, 1):
        print_stock_detail(r, rank=i)
        print()

# 买入建议
if passed:
    print('=' * 80)
    print('操作建议')
    print('=' * 80)
    for i, r in enumerate(passed[:2], 1):
        price = r['close']
        quantity = int(100000 / price / 100) * 100
        actual = quantity * price
        print('\n  {}. {} {} [{}]'.format(
            i, r['symbol'], r['name'], r['industry']))
        print('     买入{}股 @ {:.2f}元 = {:.2f}万元'.format(
            quantity, price, actual/10000))
    print('\n  买入时间: 14:50-15:00（尾盘）')
    print('  止盈: +3%  止损: -2%  次日10:00前强制清仓')

# ========== 保存CSV ==========
all_output = []
for r in passed:
    r['filter_result'] = '完全满足'
    all_output.append(r)
for r in limit_up:
    r['filter_result'] = '涨停无法买入'
    all_output.append(r)
for r in partial:
    r['filter_result'] = '涨幅>7%部分不满足'
    all_output.append(r)
for r in classic:
    r['filter_result'] = '原版策略3%-7%'
    all_output.append(r)

if all_output:
    import os
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')
    os.makedirs(output_dir, exist_ok=True)
    today_str = datetime.now().strftime('%Y%m%d')
    csv_path = os.path.join(output_dir, 'tangjie_kcb_{}.csv'.format(today_str))
    save_to_csv(all_output, csv_path)
    print('\n' + '=' * 80)
    print('结果已保存到: {}'.format(csv_path))
    print('=' * 80)

print('\n' + '=' * 80)
print('免责声明: 本选股结果仅供学习研究，不构成投资建议。')
print('股市有风险，投资需谨慎。')
print('=' * 80)
