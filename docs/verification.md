# 运行与验证

现有业务预览、资料校验及真实 HTTP 传输由 `python -m unittest discover -s tests -v` 验证；`python -m app.demo` 临时启动服务，通过消费端读取旧业务和新资料的描述输出。固定依赖的安装和容器准备方法见 README。

`RUN_ACCEPTANCE=1 python -m unittest tests.test_acceptance -v` 验证新分析消费接口的字段与信息不足契约，默认跳过。该测试不是算法正确性的证明，算法正确性由 tests.test_evidence 覆盖：预处理对撤销/修订/未来信息/同主体/拆单的处理、双交换对加权出强度与二值入度的守恒及区域/主体/自转/重复约束、锁死网络不产出假显著、BH 校正数值、seed 可复现，以及一个刻意制造超额互惠的正向对照（必须能判 excess 且通过 FDR，无方差统计必须为 untestable 而非 p=0）。

演示经 `python -m app.demo` 临时启动真实服务，对每个 study 资料同时请求 /study-preview 与 /network-evidence，完整打印输入口径、结构结果、参照抽样信息与限制，不按资料名返回静态结论；正式展示不安装依赖，三个资料的完整分析在数秒内结束（远低于 90 秒预算）。修改 app.evidence 后应同时运行 `python -m unittest discover -s tests -v`（回归）与带 RUN_ACCEPTANCE=1 的验收，并人工核对 demo 输出中 reference.held_fixed/free_to_vary 与 diagnostics.audit 是否如实描述该资料。
