import json
import unittest

from app.evidence import (
    analyze, preprocess, _rewire_week, _benjamini_hochberg, _owner_order,
    _structure_stats, MIN_REPLICATES,
)
from app.study_store import load_case


def _merchant(mid, owner, region):
    return {'id': mid, 'owner': owner, 'region': region}


def _transfer(tid, src, dst, boxes, week, known_at=None, revision=1, cancelled=False):
    return {'id': tid, 'from': src, 'to': dst, 'boxes': boxes, 'week': week,
            'known_at': week if known_at is None else known_at,
            'revision': revision, 'cancelled': cancelled}


def _case(merchants, transfers, heldout=None):
    case = {
        'kind': 'network',
        'merchants': merchants,
        'transfers': transfers,
        'as_of_week': 9,
        'allowed_region_pairs': [['east', 'east'], ['east', 'west'],
                                 ['west', 'east'], ['west', 'west']],
        'heldout_weeks': heldout or [],
        'replicates': 60,
        'seed': 42,
    }
    case['_snapshot'] = 'test-snapshot'
    return case


class PreprocessTests(unittest.TestCase):
    def test_cancelled_revised_future_and_same_owner_are_excluded(self):
        merchants = [_merchant('a', 'oA', 'east'), _merchant('a2', 'oA', 'west'),
                     _merchant('b', 'oB', 'east')]
        transfers = [
            _transfer('live', 'a', 'b', 3, 0),
            _transfer('cancel', 'a', 'b', 4, 0, cancelled=True),
            _transfer('doc-r', 'a', 'b', 2, 1, revision=1),
            _transfer('doc-r', 'a', 'b', 5, 1, revision=2),
            _transfer('future', 'a', 'b', 9, 2, known_at=10),
            _transfer('internal', 'a', 'a2', 7, 0),
        ]
        case = _case(merchants, transfers)
        _m, edge_index, _h, audit = preprocess(case)
        # cancel 被撤销（1）；同 id 的 rev1 被 rev2 取代（1），合计 2
        self.assertEqual(audit['excluded_cancelled_or_superseded'], 2)
        self.assertEqual(audit['excluded_future_knowledge'], 1)
        self.assertEqual(audit['excluded_same_owner'], 1)
        # week0 只剩 live；week1 的同 id 修订只保留 rev2（一条边，箱数更新为 5）
        self.assertEqual(len(edge_index[0]), 1)
        self.assertEqual(len(edge_index[1]), 1)
        self.assertEqual(edge_index[1][0][6], 5)
        self.assertEqual(edge_index[0][0][6], 3)

    def test_split_orders_aggregate_into_one_partner_and_one_triangle(self):
        # 同一门店对的两条拆单：聚合后互惠与三角只按一条关系计
        merchants = [_merchant('a', 'oA', 'east'), _merchant('b', 'oB', 'east'),
                     _merchant('c', 'oC', 'east')]
        transfers = [
            _transfer('s1', 'a', 'b', 2, 0),
            _transfer('s2', 'a', 'b', 3, 0),
            _transfer('back', 'b', 'a', 4, 0),
            _transfer('ac', 'a', 'c', 1, 0),
            _transfer('bc', 'b', 'c', 1, 0),
        ]
        case = _case(merchants, transfers)
        _m, edge_index, _h, audit = preprocess(case)
        self.assertEqual(audit['split_orders_aggregated'], 1)
        owner_index = _owner_order({m['id']: m for m in case['merchants']})
        stats = _structure_stats(edge_index, owner_index)
        # 一个互惠对，按两个方向各计一次 -> 2
        self.assertEqual(stats['global_reciprocal_edges'], 2)
        # 两个有向传递三角：B→A→C 与 A→B→C（共享 A→C），拆单未产生额外伙伴或三角
        self.assertEqual(stats['global_triangles'], 2)


class RewireConservationTests(unittest.TestCase):
    def test_swap_preserves_strength_region_and_owner_boundary(self):
        import random
        case = load_case('standard')
        _m, edge_index, _h, _audit = preprocess(case)
        region_allowed = {tuple(p) for p in case['allowed_region_pairs']}
        rng = random.Random(7)
        for week, edges in edge_index.items():
            new_edges, accepted = _rewire_week(edges, rng, 400, region_allowed)
            self.assertGreater(accepted, 0)
            # 加权出强度严格守恒：源门店与箱数不动
            src_before = sorted((e[0], e[6]) for e in edges)
            src_after = sorted((e[0], e[6]) for e in new_edges)
            self.assertEqual(src_before, src_after)
            # 二值入度（可交易对象数）严格守恒：每个目标门店收到的边条数不变
            indeg_before = {}
            indeg_after = {}
            for e in edges:
                indeg_before[e[1]] = indeg_before.get(e[1], 0) + 1
            for e in new_edges:
                indeg_after[e[1]] = indeg_after.get(e[1], 0) + 1
            self.assertEqual(indeg_before, indeg_after)
            # 总箱数与边数守恒
            self.assertEqual(sum(e[6] for e in edges), sum(e[6] for e in new_edges))
            self.assertEqual(len(edges), len(new_edges))
            # 区域组合始终可交易、无同主体边、无自转、无重复
            pairs = set()
            for e in new_edges:
                self.assertIn((e[4], e[5]), region_allowed)
                self.assertNotEqual(e[2], e[3])
                self.assertNotEqual(e[0], e[1])
                self.assertNotIn((e[0], e[1]), pairs)
                pairs.add((e[0], e[1]))


class LockedNetworkTests(unittest.TestCase):
    def test_fixed_case_is_marked_unvariable_and_no_fake_p_values(self):
        result = analyze(load_case('fixed'))
        self.assertFalse(result['reference']['variable'])
        self.assertTrue(all(row['p_value'] is None for row in result['structures']))
        self.assertTrue(all(row['q_value_bh'] is None for row in result['structures']))
        self.assertTrue(any('locked_constraints' in w for w in result['reference']['warnings']))
        self.assertEqual(result['multiplicity']['testable_tests'], 0)
        json.dumps(result, allow_nan=False)


class FullPipelineTests(unittest.TestCase):
    def test_standard_report_contract_and_finite_outputs(self):
        result = analyze(load_case('standard'))
        self.assertTrue(result['reference']['variable'])
        self.assertEqual(result['snapshot'], load_case('standard')['_snapshot'])
        for field in ['reference', 'structures', 'multiplicity', 'validation', 'diagnostics']:
            self.assertIn(field, result)
        for row in result['structures']:
            self.assertIn(row['direction'], {'excess', 'deficit', 'in_range', 'untestable'})
            if row['p_value'] is not None:
                # 极端尾概率（p=1）的二项标准误数学上为 0；其余应严格为正
                if row['p_value'] < 1.0:
                    self.assertGreater(row['monte_carlo_standard_error'], 0)
                else:
                    self.assertEqual(row['monte_carlo_standard_error'], 0.0)
                self.assertGreaterEqual(row['p_value'], 1 / (result['reference']['replicates'] + 1) - 1e-9)
        self.assertTrue(result['validation']['available'])
        self.assertEqual(result['validation']['heldout_weeks'], [6, 7])
        json.dumps(result, allow_nan=False)

    def test_replicates_validation(self):
        with self.assertRaises(ValueError):
            analyze(load_case('standard'), replicates=10)
        with self.assertRaises(ValueError):
            analyze(load_case('standard'), replicates=10 ** 9)

    def test_benjamini_hochberg_against_known_values(self):
        # 经典 BH 示例：p = .01,.01,.03,.65,.95，m=5
        q = _benjamini_hochberg([0.01, 0.01, 0.03, 0.65, 0.95])
        self.assertAlmostEqual(q[0], 0.025)
        self.assertAlmostEqual(q[1], 0.025)
        self.assertAlmostEqual(q[2], 0.05)
        self.assertAlmostEqual(q[3], 0.8125)
        self.assertAlmostEqual(q[4], 0.95)
        # None 保持不可检验，不占名额
        q2 = _benjamini_hochberg([None, 0.04])
        self.assertIsNone(q2[0])
        self.assertAlmostEqual(q2[1], 0.04)

    def test_reproducible_with_same_seed(self):
        r1 = analyze(load_case('edge'), replicates=MIN_REPLICATES, seed=123)
        r2 = analyze(load_case('edge'), replicates=MIN_REPLICATES, seed=123)
        r3 = analyze(load_case('edge'), replicates=MIN_REPLICATES, seed=999)
        self.assertEqual(
            [(x['structure'], x['p_value']) for x in r1['structures']],
            [(x['structure'], x['p_value']) for x in r2['structures']],
        )
        self.assertNotEqual(
            [x['p_value'] for x in r1['structures'] if x['p_value'] is not None],
            [x['p_value'] for x in r3['structures'] if x['p_value'] is not None],
        )

    def test_positive_control_detects_excess_reciprocity(self):
        # 刻意制造 3 对稳定双向互惠，应在受控参照下被判为超额（上尾）
        merchants = [_merchant('m%d' % i, 'o%d' % i, 'east') for i in range(6)]
        transfers = []
        for w in range(4):
            for a, b in [(0, 1), (2, 3), (4, 5)]:
                transfers.append(_transfer('r%d-%d-%d' % (w, a, b),
                                           'm%d' % a, 'm%d' % b, 3 + w % 2, w))
                transfers.append(_transfer('r%d-%d-%d' % (w, b, a),
                                           'm%d' % b, 'm%d' % a, 3 + w % 2, w))
        result = analyze(_case(merchants, transfers), replicates=200, seed=11)
        density = next(r for r in result['structures']
                       if r['structure'] == 'global_reciprocity_density')
        self.assertEqual(density['direction'], 'excess')
        self.assertIsNotNone(density['p_value'])
        self.assertGreater(density['monte_carlo_standard_error'], 0)
        self.assertTrue(any(r['flagged_fdr_10pct'] for r in result['structures']))
        # 参照下无方差的统计必须显式不可检验，而不是给出 p=0
        untestable = [r for r in result['structures'] if not r['testable']]
        self.assertTrue(untestable)
        self.assertTrue(all(r['p_value'] is None for r in untestable))
        self.assertTrue(all(r['direction'] == 'untestable' for r in untestable))


if __name__ == '__main__':
    unittest.main()
