[过渡] 导入层不仅是界面入口，也是运行时状态入口。import context 会把 provider 类型和导入 GPU 索引固定下来，后续控制台只消费过滤后的数据。

要点：① import context 是核心状态 ② provider_type 与 GPU 索引被持久化 ③ 控制台基于范围过滤数据
时长：1.0 分钟