源码依赖关系，核心目录可以归纳为：

```text
src/nodeskclaw_rpa_engine/
├── api/
│   ├── app.py                 FastAPI 装配、生命周期、异常映射
│   └── routes/                health、flows、workers
├── core/
│   ├── config.py              环境配置与启动约束
│   ├── health.py              readiness / liveness
│   └── logging.py             结构化日志和脱敏
├── db/
│   ├── session.py             Async SQLAlchemy
│   └── models/
│       ├── flow.py            Flow、Version、Validation、Audit
│       ├── execution.py       Worker、Attempt、Callback Outbox
│       └── browser.py         Browser Profile、CDP Endpoint 预留
├── flows/
│   ├── manifest.py            Flow Manifest 协议
│   ├── package.py             ZIP、AST、安全策略校验
│   ├── service.py             Registry 生命周期
│   └── repository.py          Registry 数据访问
├── workers/
│   ├── pool.py                Worker 状态、并发、调度、续租
│   ├── source.py              Lease 命令源
│   ├── resolver.py            精确版本解析
│   ├── task_client.py         Task Worker API Client
│   └── outbox.py              EVENT / FINISH 可靠投递
├── runtime/
│   ├── engine.py              RPA 执行主循环
│   ├── loader.py              Flow 下载、缓存、动态加载
│   ├── browser.py             Playwright 浏览器生命周期
│   ├── context.py             Flow 能力注入
│   ├── artifacts.py           截图、下载、Trace
│   └── errors.py              错误分类与终态映射
├── mock_srm/                  本地确定性 Portal
└── main.py                    应用入口
```

数据库基线共包含九个 Engine 所有的模型：Flow、Flow Version、Validation Run、Release Audit、Worker Instance、Execution Attempt、Callback Outbox、Browser Profile、CDP Endpoint。