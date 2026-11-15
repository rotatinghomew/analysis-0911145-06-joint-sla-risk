# 产品数据与调用约定

merchants 的 owner 是共同经营主体，region 是可交易机会的门店位置；转主体后仍需保留原门店证据以检验 allowed_region_pairs。transfers 以 id/revision 记录更正和撤销，known_at 晚于 as_of_week 的记录不可见。boxes 是整数箱数，有向边；同主体内部调拨不作为跨商户互惠。heldout_weeks 不参与结构筛选。接口 POST /network-evidence 接收 {case, replicates?, seed?}，返回 {snapshot, reference, structures, multiplicity, validation, diagnostics}。reference 明确守恒量、结构零及抽样有效性；structures 区分效应量、随机检验不确定性和无法检验，不要求任何商户显著。

现有 GET /health、GET /cases 和 POST /preview 保留原有资料预览。新增 GET /study-cases 和 POST /study-preview {case} 已可用，只校验与描述 data/study 的资料；推断消费路由 POST /network-evidence 已接通，由 app.evidence.analyze 计算，不按资料名返回静态结论。app.client.analysis 指向上文约定的新消费接口。所有 snapshot 都是相应原始资料字节的 SHA-256，输出仅使用有限 JSON 数值，无法判断用明确状态与 null 表达，不得返回 NaN。资料只供本地分析，不连接外部服务。

## 结构零（参照网络）固定什么、可变什么

参照由逐周有向 2-switch 双交换抽样得到（app.evidence），周与周独立重配，不做无向化，不跨周交换时间先后。

严格守恒（held_fixed）：每个源门店每周的加权出强度（出货箱数，即交易规模）与每条边的箱数；每个门店的二值出度/入度（可交易对象数量）；allowed_region_pairs 区域组合；owner 主体边界（同老板门店互调不算跨商户伙伴）；禁自转、禁重复边、边数与总箱数。门店边先重配，再聚合到主体层，因此同一老板的多个门店始终只算一个伙伴，拆单在周/主体层合并，不会制造三角或虚增伙伴。

可变空间（free_to_vary）：在上述守恒量下，源门店与谁建立有向联系；互惠对、传递三角、二路径中介的具体构成；各目标门店的加权入箱数。加权有向图不存在同时严格守恒加权出/入强度的二交换，因此加权入强度被保留为可变空间而非强行锁死；二值入度仍严格守恒。

reference 含 variable 布尔值。若任何一周都没有可接受交换（约束把空间锁死），variable=false，全部 structures 的 p_value/q_value_bh 为 null，direction=untestable，并在 reference.warnings 与 diagnostics.warnings 给出 locked_constraints，不用零表示无证据。

## 随机检验、误差与多重性

p_value 是 plus-one 蒙特卡洛上尾概率 (exceed+1)/(replicates+1)，永远不会因有限模拟报成 0；每个可检验行同时给 monte_carlo_standard_error（二项标准误）、reference_mean/reference_sd、z_score 与 effect_ratio_observed_over_reference。reference.monte_carlo_resolution 给出最小可分辨 p，末位小数不得当作精确名次。replicates 允许 50..10000，默认取资料内 replicates（合成资料为 200）；seed 控制 RNG，同 seed 结果可复现。

multiplicity 用 Benjamini-Hochberg（在全精度 p 上计算，输出 q_value_bh 为舍入值），无法检验的结构不占检验族名额。flagged_fdr_10pct 仅在 q≤0.10 且可检验时为真。

## 后续周持续检验（validation）

heldout_weeks 用独立 RNG 流单独重抽参照，不参与训练期筛选。validation.rows 按 structure/owner/metric 给出后续周 observed、reference_mean、testable、upper_tail_percentile 与 persists（可检验且上尾分位≤0.1）。structures 每行回挂 heldout_persists 与 heldout_upper_tail_percentile；无 heldout 周时 available=false 且对应字段为 null。

## 预处理审计（diagnostics.audit 与 warnings）

records_total、excluded_future_knowledge（known_at 晚于 as_of_week）、excluded_cancelled_or_superseded（撤销单与被更高 revision 取代的旧修订）、excluded_same_owner（同主体内部调拨）、split_orders_aggregated（同周同门店对的重复单据计数）。当唯一参照构型占比偏低或交换接受率过低时，warnings 给出 limited_exploration/low_swap_acceptance，提示抽样可能未充分展开。
