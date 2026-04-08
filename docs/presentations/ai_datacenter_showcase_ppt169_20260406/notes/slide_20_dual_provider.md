[过渡] 平台之所以能够同时兼容部署 Agent 和不部署 Agent 的机器，是因为内部做了 provider 抽象。Agent 和 SSH Linux 两条链路都被纳入统一运行时模型。

要点：① 双 provider 架构 ② Agent 与 SSH 模式并行 ③ 对外保持同一产品流程
时长：1.0 分钟