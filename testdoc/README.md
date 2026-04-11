# testdoc 入口

当前主文件：

- `作品报告_网页叙事版.html`：按大赛模板六章结构写成的网页作品书。
- `04-3 作品报告（大数据应用赛，2025版）模板.docx`：原模板。

支撑文件：

- `data/report_book_metrics.json`：作品书图表所用的代码统计与示例数据。
- `scripts/generate_report_book_assets.py`：重新生成作品书图表的脚本。
- `assets/report_book.css`：网页作品书样式。
- `assets/book_*.svg`：作品书图表资源。

双 GPU 并发竞争治理实验：

- `scripts/real_remote_dual_gpu_competition.py`：真实远端双 GPU 并发实验脚本。
- `scripts/real_remote_dual_gpu_competition_charts.py`：根据实验 JSON 生成多维对比图。
- `data/real_remote_dual_gpu_competition.json`：实验完整结果，含治理对象、预算动作、时延与汇总。
- `data/real_remote_dual_gpu_competition_samples.csv`：逐点原始样本。
- `data/real_remote_dual_gpu_competition_summary.csv`：按角色与阶段汇总的裁判快读表。
- `assets/dual_gpu_competition_timeline.svg`：双卡功耗时间线图。
- `assets/dual_gpu_competition_comparison.svg`：治理卡与对照卡多指标对比图。
- `assets/dual_gpu_competition_latency.svg`：治理时延与后窗清洁率图。

实验口径：

- 两张 GPU 在同一台主机上同时启动相同负载。
- 仅对治理 GPU 通过系统预算调度链路下发 `set_power_limit`。
- 若预算动作同时命中对照 GPU，脚本会直接判失败，不会产出“看起来好看”的结果。

检查点恢复实验：

- `scripts/real_remote_checkpoint_restore_experiment.py`：真实远端双 GPU 检查点恢复实验脚本，当前通过 `ssh_linux` 路径执行暂停、检查点写出和跨卡恢复。
- `scripts/real_remote_checkpoint_restore_charts.py`：根据实验 JSON 生成恢复时间线、进度连续性和效果压缩图。
- `data/real_remote_checkpoint_restore_experiment.json`：实验完整结果，含源卡/目标卡、暂停与恢复状态、检查点清单和逐阶段样本。
- `data/real_remote_checkpoint_restore_samples.csv`：10 个原始样本点，覆盖源卡运行、暂停窗口、检查点就绪、目标卡恢复窗口。
- `data/real_remote_checkpoint_restore_summary.csv`：裁判快读表，汇总冻结增量、恢复增量、检查点步数和切换时延。
- `assets/checkpoint_restore_timeline.svg`：源卡与目标卡负载切换时间线。
- `assets/checkpoint_restore_progress.svg`：进度连续性图，展示检查点步数与恢复后步数。
- `assets/checkpoint_restore_comparison.svg`：暂停、恢复与跨卡切换的多维压缩图。

实验口径：

- 在源 GPU 上启动带进度文件与检查点文件契约的高负载任务。
- 先通过 `ssh_linux` 的进程控制能力执行 `pause / resume`，观察进度冻结与恢复。
- 再触发检查点写出，终止源卡任务，并在目标 GPU 上基于 manifest 恢复继续执行。
- 若恢复后进度回到 0、目标卡未接手，或源卡残留运行，则实验直接判失败。
