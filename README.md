# 受交易机会约束的商户调货互惠与中介结构检验

本地分析工作台保留已有业务资料与预览能力，并提供独立分析资料的校验、HTTP 预览与结构证据推断。`data/study` 保存本地合成资料，`app/study.py` 解释资料结构，`app/evidence.py` 在控制交易规模、可交易对象与周别机会后检验互惠与中介是否超出随机参照；出货量榜本身不作为协作证据。

数据均为本地合成，不含真实姓名、电话号码或生产系统凭据。`standard` 是常规资料，`edge` 用于检查信息不足或约束冲突，`fixed` 是约束把参照空间完全锁死的资料。它们只描述观测，不预设分析结论。

## 本地使用

Python 3.11，依赖版本固定在 `requirements.txt`。NumPy/SciPy 是分析工作台的数值工具；预览逻辑主要使用标准库。准备阶段安装依赖，仓库不在启动或测试时下载任何资源。

支持 Python 3.11 系列的补丁版本；Docker 基础镜像通过 SHA256 固定为 Python 3.11.14，依赖清单保持精确版本。相同依赖还需在非 root 的 Python 3.11.2 Linux 环境中验证，应用不依赖特定补丁版本。

```sh
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m app.demo
python -m app.server
```

服务监听 `127.0.0.1:8080`，也可通过 `PORT` 调整。预览请求由 `app/client.py` 发起；`app.demo` 在临时端口启动真实服务并完整打印现有业务输出，不是录制日志的回放。服务接口和数据文件的可见性约定不能互相替代。

## 可复现环境

```sh
docker build -t local/joint-sla-risk:baseline .
docker run --rm --network none local/joint-sla-risk:baseline python -m unittest discover -s tests -v
docker run --rm --network none local/joint-sla-risk:baseline
```

准备阶段允许构建镜像和预装依赖；正式演示不进行构建或安装。演示通过真实 HTTP 调用展示旧业务预览、study 资料描述与 /network-evidence 结构证据（含参照守恒量、随机检验误差、多重性与后续周持续检验），保留完整输出；三个资料在数秒内结束。功能测试启用方式：`RUN_ACCEPTANCE=1 python -m unittest tests.test_acceptance -v`，默认跳过验收测试，算法层面的可核对计算与正向/锁死对照在 tests.test_evidence 中默认运行。
