"""结构证据分析：在交易规模、可交易对象与周别机会受控后，
检验互惠与中介关系是否仍超出随机参照。

参照网络（结构零）通过逐周有向 2-switch 双交换生成，严格保持：
每个源门店每周的加权出强度（出货箱数=交易规模）、每个门店的二值
出度/入度（可交易对象数量）、区域可交易约束、主体边界（同一老板的
门店之间不产生跨主体边）、边数与总箱数，以及边的方向性；周与周独立
重配，时间先后不被抹成无向图。加权入强度在固定入度与出强度下保留为
可变空间（加权有向图不存在同时严格守恒加权出入强度的二交换）。

约束把空间锁死（没有任何可接受交换）时不硬算显著性，对应 p_value 为 null。
蒙特卡洛结果一律带抽样误差，不输出虚假精度。
"""
import hashlib
import random

from app.study import validate, current_transfers

MIN_REPLICATES = 50
MAX_REPLICATES = 10000
DEFAULT_REPLICATES = 200
SWAPS_PER_EDGE = 8
# 唯一构型占比低于该阈值时提示参照探索不充分
EXPLORE_WARN_RATIO = 0.5


def _round(value, digits=4):
    if value is None:
        return None
    return round(float(value), digits)


def _safe_ratio(numerator, denominator):
    return float(numerator) / float(denominator) if denominator else 0.0


def preprocess(case):
    """按信息截止、修订/撤销、主体边界整理记录，并按周分层。

    撤销单与被取代的修订不进入网络；同一老板的多个门店在聚合后
    只是一个伙伴，同主体内调拨不参与跨主体结构；拆单在周/主体
    层面聚合，不会把一条关系拆成多条边来制造三角。
    """
    merchants = validate(case)
    heldout = set(case['heldout_weeks'])

    records = case['transfers']
    total = len(records)
    future = sum(1 for t in records if t['known_at'] > case['as_of_week'])
    current = current_transfers(case)
    cancelled_or_revised = total - future - len(current)

    internal = 0
    split_pairs = 0
    weeks = {}
    for t in current:
        src = merchants[t['from']]
        dst = merchants[t['to']]
        if src['owner'] == dst['owner']:
            internal += 1
            continue
        w = t['week']
        bucket = weeks.setdefault(w, {'edges': [], 'pairs': set()})
        bucket['edges'].append((src['id'], dst['id'], src['owner'], dst['owner'],
                                src['region'], dst['region'], int(t['boxes'])))
        pair_key = (src['id'], dst['id'])
        if pair_key in bucket['pairs']:
            split_pairs += 1
        bucket['pairs'].add(pair_key)

    analysis_weeks = sorted(w for w in weeks if w not in heldout)
    heldout_weeks = sorted(w for w in weeks if w in heldout)
    edge_index = {w: list(weeks[w]['edges']) for w in analysis_weeks}
    heldout_index = {w: list(weeks[w]['edges']) for w in heldout_weeks}

    audit = {
        'records_total': total,
        'excluded_future_knowledge': future,
        'excluded_cancelled_or_superseded': cancelled_or_revised,
        'excluded_same_owner': internal,
        'split_orders_aggregated': split_pairs,
        'analysis_weeks': analysis_weeks,
        'heldout_weeks': heldout_weeks,
    }
    return merchants, edge_index, heldout_index, audit


def _owner_order(merchants):
    owners = sorted({m['owner'] for m in merchants.values()})
    return {owner: i for i, owner in enumerate(owners)}


def _flows(edges, owner_index):
    """把门店层有向边聚合为主体层周流量（拆单在此合并）。"""
    n = len(owner_index)
    flow = [[0] * n for _ in range(n)]
    for _sid, _did, src_owner, dst_owner, _sr, _dr, boxes in edges:
        flow[owner_index[src_owner]][owner_index[dst_owner]] += boxes
    return flow


def _structure_stats(edge_index, owner_index):
    """计算全部候选结构统计量。

    互惠（dyad_reciprocal）：成对主体双向都有往来，方向性保留；
    三角（transitive_triangle）：以 i 为中间顶点的有向传递三元组
    h→i→k 且 h→k，仅在同一周内计，每个有向三角按中间顶点唯一计数；
    撤销/拆单在聚合阶段已处理，无法跨周凭空拼出；
    中介（brokerage）：以某主体为中间人的有向二路径 h→i→k（h≠k）。
    """
    n = len(owner_index)
    rec_obs = [0] * n
    tri_obs = [0] * n
    brok_obs = [0] * n
    rec_flow_obs = [0] * n
    tri_flow_obs = [0] * n
    brok_flow_obs = [0] * n
    global_rec_edges = 0
    global_tri = 0
    global_dyads = 0
    edges_total = 0
    boxes_total = 0

    for week in sorted(edge_index):
        flow = _flows(edge_index[week], owner_index)
        edges_total += sum(1 for i in range(n) for j in range(n) if flow[i][j] > 0)
        boxes_total += sum(sum(row) for row in flow)
        for i in range(n):
            out_i = [j for j in range(n) if j != i and flow[i][j] > 0]
            in_i = [j for j in range(n) if j != i and flow[j][i] > 0]
            for j in out_i:
                global_dyads += 1
                if flow[j][i] > 0:
                    rec_obs[i] += 1
                    rec_flow_obs[i] += min(flow[i][j], flow[j][i])
                    global_rec_edges += 1
            # 中介：i 作为中间人，h→i→k
            for h in in_i:
                for k in out_i:
                    if h == k:
                        continue
                    brok_obs[i] += 1
                    brok_flow_obs[i] += min(flow[h][i], flow[i][k])
            # 传递三角（i 为中间顶点）：h→i→k 且 h→k；
            # 每个有向三角按其中间顶点唯一计数，不重复
            for h in in_i:
                for k in out_i:
                    if h == k or flow[h][k] <= 0:
                        continue
                    tri_obs[i] += 1
                    tri_flow_obs[i] += min(flow[h][i], flow[i][k], flow[h][k])
                    global_tri += 1

    return {
        'dyad_reciprocal': (rec_obs, rec_flow_obs),
        'transitive_triangle': (tri_obs, tri_flow_obs),
        'brokerage': (brok_obs, brok_flow_obs),
        'global_reciprocal_edges': global_rec_edges,
        'global_dyads': global_dyads,
        'global_triangles': global_tri,
        'edges_total': edges_total,
        'boxes_total': boxes_total,
    }


def _empty_stat_arrays(owner_index):
    n = len(owner_index)
    zeros = [0] * n
    return {
        'dyad_reciprocal': (list(zeros), list(zeros)),
        'transitive_triangle': (list(zeros), list(zeros)),
        'brokerage': (list(zeros), list(zeros)),
        'global_reciprocal_edges': 0,
        'global_dyads': 0,
        'global_triangles': 0,
        'edges_total': 0,
        'boxes_total': 0,
    }


def _rewire_week(edges, rng, swaps, region_allowed):
    """对一周的门店层有向加权边做 2-switch 双交换。

    取两条边 A→B（箱数 x）与 C→D（箱数 y），交换目标门店：
    A→B 改为 A→D（箱数仍为 x），C→D 改为 C→B（箱数仍为 y）。
    于是源门店 A、C 的出货箱数不变（加权出强度守恒），每个目标门店
    收到的边条数不变（二值入度守恒）；B、D 收到的箱数 x/y 互换，故
    加权入强度保留为可变空间。边数与总箱数不变。
    区域可交易组合、禁自转、禁同主体边、禁重复边继续生效。
    返回 (新边表, 接受次数)。
    """
    work = [list(e) for e in edges]
    accepted = 0
    if len(work) < 2:
        return work, accepted
    for _ in range(swaps):
        i, j = rng.sample(range(len(work)), 2)
        a, c = work[i], work[j]
        # 边结构：[源id, 目标id, 源owner, 目标owner, 源region, 目标region, 箱数]
        if a[0] == c[0] or a[1] == c[1]:
            continue
        # 新边 A→D 与 C→B 的区域组合必须仍可交易
        if (a[4], c[5]) not in region_allowed:
            continue
        if (c[4], a[5]) not in region_allowed:
            continue
        # 禁自转
        if a[0] == c[1] or c[0] == a[1]:
            continue
        # 主体边界：新边不得落入同一老板内部
        if a[2] == c[3] or c[2] == a[3]:
            continue
        existing = {(e[0], e[1]) for e in work}
        existing.discard((a[0], a[1]))
        existing.discard((c[0], c[1]))
        if (a[0], c[1]) in existing or (c[0], a[1]) in existing:
            continue
        # 交换目标及其派生属性（目标id/目标owner/目标region = 索引1/3/5）；
        # 源（0/2/4）与箱数（6）不动
        a[1], c[1] = c[1], a[1]
        a[3], c[3] = c[3], a[3]
        a[5], c[5] = c[5], a[5]
        accepted += 1
    return work, accepted


def _config_signature(edge_index):
    parts = []
    for week in sorted(edge_index):
        signature = tuple(sorted((e[0], e[1], e[6]) for e in edge_index[week]))
        parts.append((week, signature))
    return hashlib.sha256(repr(parts).encode()).hexdigest()


def _simulate(base_index, owner_index, region_allowed, replicates, seed):
    """生成参照网络样本并计算每个样本的结构统计量。"""
    rng = random.Random(seed)
    weeks = sorted(base_index)
    swaps_per_week = {w: max(1, len(base_index[w]) * SWAPS_PER_EDGE) for w in weeks}

    samples = []
    accepted_total = 0
    attempts_total = 0
    signatures = set()
    for _ in range(replicates):
        simulated = {}
        for w in weeks:
            new_edges, accepted = _rewire_week(
                base_index[w], rng, swaps_per_week[w], region_allowed)
            simulated[w] = new_edges
            accepted_total += accepted
            attempts_total += swaps_per_week[w]
        signatures.add(_config_signature(simulated))
        samples.append(_structure_stats(simulated, owner_index))
    return samples, {
        'accepted_swaps': accepted_total,
        'attempted_swaps': attempts_total,
        'unique_configurations': len(signatures),
        'weeks_simulated': len(weeks),
    }


def _benjamini_hochberg(p_values):
    """BH 校正；无法检验的 None 保留为 None，不占检验族名额。"""
    finite = [(i, p) for i, p in enumerate(p_values) if p is not None]
    adjusted = [None] * len(p_values)
    if not finite:
        return adjusted
    order = sorted(range(len(finite)), key=lambda k: finite[k][1])
    m = len(finite)
    previous = 1.0
    for rank in range(m, 0, -1):
        idx, p = finite[order[rank - 1]]
        value = min(previous, p * m / rank)
        previous = value
        adjusted[idx] = min(1.0, value)
    return adjusted


def _monte_carlo_row(observed, null_values, replicates):
    null_mean = sum(null_values) / replicates
    variance = sum((v - null_mean) ** 2 for v in null_values) / replicates
    sd = variance ** 0.5
    exceed = sum(1 for v in null_values if v >= observed)
    # plus-one 校正：p 不会因有限模拟被报告成 0
    p_value = (exceed + 1) / (replicates + 1)
    mc_se = (p_value * (1 - p_value) / (replicates + 1)) ** 0.5
    testable = variance > 0
    z = ((observed - null_mean) / sd) if testable and sd > 0 else None
    ratio = (observed / null_mean) if null_mean > 0 else None
    return {
        'observed': observed,
        'reference_mean': _round(null_mean, 3),
        'reference_sd': _round(sd, 3),
        'p_value': _round(p_value) if testable else None,
        'p_value_raw': p_value if testable else None,
        'monte_carlo_standard_error': _round(mc_se) if testable else None,
        'z_score': _round(z, 3) if z is not None else None,
        'effect_ratio_observed_over_reference': _round(ratio, 3) if ratio is not None else None,
        'testable': testable,
    }


def _structure_rows(stats_obs, samples, replicates, owners, family, key):
    rows = []
    count_obs, flow_obs = stats_obs[key]
    for i, owner in enumerate(owners):
        null_counts = [s[key][0][i] for s in samples]
        null_flows = [s[key][1][i] for s in samples]
        count_row = _monte_carlo_row(count_obs[i], null_counts, replicates)
        flow_row = _monte_carlo_row(flow_obs[i], null_flows, replicates)
        testable = count_row['testable'] or flow_row['testable']
        rows.append({
            'structure': family,
            'unit': 'owner',
            'owner': owner,
            'metric': 'count',
            'family': family,
            **count_row,
        })
        rows.append({
            'structure': family,
            'unit': 'owner',
            'owner': owner,
            'metric': 'weighted_boxes',
            'family': family,
            **flow_row,
        })
    return rows


def _global_rows(stats_obs, samples, replicates):
    rows = []
    for label, obs_key in [('global_reciprocal_edges', 'global_reciprocal_edges'),
                           ('global_transitive_triangles', 'global_triangles')]:
        observed = stats_obs[obs_key]
        null_values = [s[obs_key] for s in samples]
        rows.append({
            'structure': label,
            'unit': 'network',
            'owner': None,
            'metric': 'count',
            'family': 'global',
            **_monte_carlo_row(observed, null_values, replicates),
        })
    # 全局互惠密度：双向边占有向边的比例，受控于强度与机会后的净互惠倾向
    obs_ratio = _safe_ratio(stats_obs['global_reciprocal_edges'], stats_obs['global_dyads'])
    null_ratio = [_safe_ratio(s['global_reciprocal_edges'], s['global_dyads']) for s in samples]
    rows.append({
        'structure': 'global_reciprocity_density',
        'unit': 'network',
        'owner': None,
        'metric': 'ratio',
        'family': 'global',
        **_monte_carlo_ratio_row(obs_ratio, null_ratio, replicates),
    })
    return rows


def _monte_carlo_ratio_row(observed, null_values, replicates):
    null_mean = sum(null_values) / replicates
    variance = sum((v - null_mean) ** 2 for v in null_values) / replicates
    sd = variance ** 0.5
    exceed = sum(1 for v in null_values if v >= observed)
    p_value = (exceed + 1) / (replicates + 1)
    mc_se = (p_value * (1 - p_value) / (replicates + 1)) ** 0.5
    testable = variance > 0
    z = ((observed - null_mean) / sd) if testable and sd > 0 else None
    return {
        'observed': _round(observed),
        'reference_mean': _round(null_mean),
        'reference_sd': _round(sd),
        'p_value': _round(p_value) if testable else None,
        'p_value_raw': p_value if testable else None,
        'monte_carlo_standard_error': _round(mc_se) if testable else None,
        'z_score': _round(z, 3) if z is not None else None,
        'effect_ratio_observed_over_reference': _round(observed / null_mean, 3) if null_mean > 0 else None,
        'testable': testable,
    }


def _direction(row):
    if not row['testable'] or row['p_value_raw'] is None:
        return 'untestable'
    p = row['p_value_raw']
    if p <= 0.1:
        return 'excess'
    if p >= 0.9:
        return 'deficit'
    return 'in_range'


def _persistence(heldout_index, owner_index, region_allowed, replicates, base_seed):
    """用后来的调货周（heldout）做持续检验：参照分布独立重抽，
    只看训练期识别出的结构在后续周是否仍处在参照上尾。"""
    if not heldout_index:
        return {'heldout_weeks': [], 'available': False, 'rows': []}
    samples, sim_info = _simulate(
        heldout_index, owner_index, region_allowed, replicates, base_seed + 1)
    stats_hold = _structure_stats(heldout_index, owner_index)
    owners = sorted(owner_index, key=lambda o: owner_index[o])

    rows = []
    for family, key in [('dyad_reciprocal', 'dyad_reciprocal'),
                        ('transitive_triangle', 'transitive_triangle'),
                        ('brokerage', 'brokerage')]:
        count_obs, flow_obs = stats_hold[key]
        for i, owner in enumerate(owners):
            for metric, obs_vals, null_idx in [
                ('count', count_obs, 0),
                ('weighted_boxes', flow_obs, 1),
            ]:
                null_values = [s[key][null_idx][i] for s in samples]
                null_mean = sum(null_values) / replicates
                variance = sum((v - null_mean) ** 2 for v in null_values) / replicates
                testable = variance > 0
                percentile = None
                if testable:
                    ge = sum(1 for v in null_values if v >= obs_vals[i])
                    percentile = _round(ge / replicates)
                rows.append({
                    'structure': family,
                    'owner': owner,
                    'metric': metric,
                    'observed': obs_vals[i],
                    'reference_mean': _round(null_mean, 3),
                    'testable': testable,
                    'upper_tail_percentile': percentile,
                    'persists': bool(testable and percentile is not None and percentile <= 0.1),
                })
    return {
        'heldout_weeks': sorted(heldout_index),
        'available': True,
        'rows': rows,
        'sampling': sim_info,
    }


def analyze(case, replicates=None, seed=None):
    """主入口：返回符合消费契约的结构证据报告。"""
    region_allowed = {tuple(pair) for pair in case['allowed_region_pairs']}
    replicates = int(replicates if replicates is not None else case.get('replicates', DEFAULT_REPLICATES))
    if not MIN_REPLICATES <= replicates <= MAX_REPLICATES:
        raise ValueError('replicates 超出允许范围 %d..%d' % (MIN_REPLICATES, MAX_REPLICATES))
    seed = int(seed if seed is not None else case.get('seed', 0))

    merchants, edge_index, heldout_index, audit = preprocess(case)
    owner_index = _owner_order(merchants)
    owners = sorted(owner_index, key=lambda o: owner_index[o])

    stats_obs = (_structure_stats(edge_index, owner_index)
                 if edge_index else _empty_stat_arrays(owner_index))

    no_room = not edge_index or all(len(e) < 2 for e in edge_index.values())
    if no_room:
        samples = [_empty_stat_arrays(owner_index) for _ in range(replicates)]
        sim_info = {'accepted_swaps': 0, 'attempted_swaps': 0,
                    'unique_configurations': 1, 'weeks_simulated': len(edge_index)}
    else:
        samples, sim_info = _simulate(edge_index, owner_index, region_allowed,
                                      replicates, seed)

    variable = sim_info['accepted_swaps'] > 0

    rows = []
    rows += _structure_rows(stats_obs, samples, replicates, owners,
                            'dyad_reciprocal', 'dyad_reciprocal')
    rows += _structure_rows(stats_obs, samples, replicates, owners,
                            'transitive_triangle', 'transitive_triangle')
    rows += _structure_rows(stats_obs, samples, replicates, owners,
                            'brokerage', 'brokerage')
    rows += _global_rows(stats_obs, samples, replicates)

    # 约束锁死时，参照分布没有方差，任何行都不可检验
    if not variable:
        for row in rows:
            row['testable'] = False
            row['p_value'] = None
            row['p_value_raw'] = None
            row['monte_carlo_standard_error'] = None
            row['z_score'] = None

    # BH 校正基于全精度 p，避免用舍入后的 p 反推 q
    raw_p = [row['p_value_raw'] for row in rows]
    q_values = _benjamini_hochberg(raw_p)
    for row, q in zip(rows, q_values):
        row['q_value_bh'] = _round(q) if q is not None else None
        row['q_value_bh_raw'] = q
        row['direction'] = _direction(row)
        row['flagged_fdr_10pct'] = bool(
            row['testable'] and row['q_value_bh_raw'] is not None
            and row['q_value_bh_raw'] <= 0.10)

    testable_count = sum(1 for row in rows if row['testable'])
    multiplicity = {
        'method': 'Benjamini-Hochberg',
        'family_size': len(rows),
        'testable_tests': testable_count,
        'untestable_tests': len(rows) - testable_count,
        'fdr_level': 0.10,
        'note': '无法检验的结构不占检验族名额；q_value_bh 为 null 表示参照无方差而非无证据',
    }

    validation = _persistence(heldout_index, owner_index, region_allowed,
                              replicates, seed)
    if validation['available']:
        lookup = {(r['structure'], r['owner'], r['metric']): r for r in validation['rows']}
        for row in rows:
            if row['unit'] != 'owner':
                continue
            hold = lookup.get((row['structure'], row['owner'], row['metric']))
            row['heldout_persists'] = hold['persists'] if hold else None
            row['heldout_upper_tail_percentile'] = (
                hold['upper_tail_percentile'] if hold else None)
    else:
        for row in rows:
            row['heldout_persists'] = None
            row['heldout_upper_tail_percentile'] = None

    warnings = []
    if not variable:
        warnings.append('locked_constraints: 约束下不存在可接受交换，参照网络唯一，全部结构无法检验显著性')
    else:
        ratio = sim_info['unique_configurations'] / replicates
        if ratio < EXPLORE_WARN_RATIO:
            warnings.append('limited_exploration: 唯一参照构型占比 %.2f，抽样可能未充分展开' % ratio)
        acceptance = _safe_ratio(sim_info['accepted_swaps'], sim_info['attempted_swaps'])
        if acceptance < 0.05:
            warnings.append('low_swap_acceptance: 交换接受率 %.3f，约束较强，参照空间可能狭小' % acceptance)
    if audit['excluded_cancelled_or_superseded']:
        warnings.append('records_cancelled_or_superseded_excluded: %d 条撤销/旧修订未参与结构'
                        % audit['excluded_cancelled_or_superseded'])
    if audit['excluded_same_owner']:
        warnings.append('same_owner_transfers_excluded: %d 条同主体内部调拨未算作跨商户伙伴'
                        % audit['excluded_same_owner'])
    if audit['split_orders_aggregated']:
        warnings.append('split_orders_aggregated: %d 条重复门店对已按周聚合，不制造三角'
                        % audit['split_orders_aggregated'])

    reference = {
        'null_model': 'stratified_directed_double_edge_swap',
        'held_fixed': [
            '每个源门店每周的出货箱数（加权出强度=交易规模）与每条边的箱数',
            '每个门店的二值出度与入度（可交易对象的数量）',
            '每周内的有向边集合与边方向（不做无向化，周间不互换时间先后）',
            'allowed_region_pairs 区域可交易组合',
            'owner 主体边界：同一老板的门店互调不算跨商户伙伴',
            '禁自转、禁重复边、边数与总箱数；门店边先重配再聚合到主体层，拆单不产生新伙伴',
        ],
        'free_to_vary': [
            '在上述守恒量下，出货门店与谁建立有向联系（伙伴身份可重配）',
            '互惠对、传递三角与二路径中介的具体构成',
            '各目标门店的加权入箱数（在固定入度与出强度下仍可变化；加权有向图不存在同时严格守恒加权出入强度的二交换，这是本参照的已知可变空间而非缺陷）',
        ],
        'variable': variable,
        'replicates': replicates,
        'seed': seed,
        'swaps_per_edge': SWAPS_PER_EDGE,
        'sampling': sim_info,
        'monte_carlo_resolution': {
            'minimum_nontrivial_p': _round(1 / (replicates + 1)),
            'note': 'p 值为 plus-one 蒙特卡洛上尾概率，附带二项标准误；不要把末位小数当作精确名次',
        },
        'warnings': warnings,
    }

    diagnostics = {
        'audit': audit,
        'warnings': warnings,
        'observed_network': {
            'owners': len(owners),
            'analysis_edges': stats_obs['edges_total'],
            'analysis_boxes': stats_obs['boxes_total'],
            'global_reciprocal_edges': stats_obs['global_reciprocal_edges'],
            'global_transitive_triangles': stats_obs['global_triangles'],
        },
        'heldout_available': validation['available'],
    }

    # 移除仅供内部计算的全精度字段，输出仅保留契约规定的舍入值
    public_rows = []
    for row in rows:
        public_rows.append({k: v for k, v in row.items()
                            if k not in ('p_value_raw', 'q_value_bh_raw')})

    return {
        'snapshot': case['_snapshot'],
        'reference': reference,
        'structures': public_rows,
        'multiplicity': multiplicity,
        'validation': {k: v for k, v in validation.items() if k != 'rows'} | {
            'rows': validation['rows']},
        'diagnostics': diagnostics,
    }
