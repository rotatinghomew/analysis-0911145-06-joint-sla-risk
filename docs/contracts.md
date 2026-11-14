# 产品数据与调用约定

merchants 的 owner 是共同经营主体，region 是可交易机会的门店位置；转主体后仍需保留原门店证据以检验 allowed_region_pairs。transfers 以 id/revision 记录更正和撤销，known_at 晚于 as_of_week 的记录不可见。boxes 是整数箱数，有向边；同主体内部调拨不作为跨商户互惠。heldout_weeks 不参与结构筛选。新接口 POST /network-evidence 接收 {case, replicates?, seed?}，返回 {snapshot, reference, structures, multiplicity, validation, diagnostics}。reference 明确守恒量、结构零及抽样有效性；structures 区分效应量、随机检验不确定性和无法检验，不要求任何商户显著。

现有 GET /health、GET /cases 和 POST /preview 保留原有资料预览。新增 GET /study-cases 和 POST /study-preview {case} 已可用，只校验与描述 data/study 的资料；推断消费路由尚未实现。app.client.analysis 指向上文约定的新消费接口。所有 snapshot 都是相应原始资料字节的 SHA-256，输出仅使用有限 JSON 数值，无法判断用明确状态与 null 表达，不得返回 NaN。资料只供本地分析，不连接外部服务。

reference 含 variable 布尔值，表示给定约束下网络结构是否仍有可变空间；structures 每项含 p_value，无法合法检验时为 null，不用零表示无证据。
