# 产品数据与调用约定

shipments 的 duration_lower 是已知耗时下界，complete=false 时上界未知；complete=true 的 duration_upper 与 lower 相同。environment 同一值代表同批共同外部条件。route_segments 含共享 hub 段，备选 route 不是同车重复观测。thresholds 以小时计，是客户端输入；评价总体为 demand 中的固定目的地权重。POST /joint-risk {case, thresholds?, routes?} 返回 {snapshot, marginal, joint, alternatives, diagnostics}。joint 分清 any_late、late_count、tail_delay 的定义与识别范围，缺测不等同准时或违约。比较必须说明需求是否在两套方案共同支持范围。

当前 GET /cases、POST /preview 和 GET /health 已可用；client.analysis 是待接入的业务消费调用，新分析路由尚不存在。原始数据通过 app.store 读取，snapshot 为输入字节的 SHA-256。新增接口须保留现有预览能力和 JSON 有限数值约定。

joint.any_late 使用 {estimate, lower, upper}，estimate 可为空，lower/upper 是明确给出含义的概率区间。统计不确定性和依赖假设敏感性应区分；任一设定下都不能违反已知的非负耗时支撑。
