# Performance Hotpath Optimization Design

## Goal

Reduce latency and CPU/IO overhead in the backend collection loop, SQLite hot paths, agent-side process/system sampling, replay frame generation, and frontend high-frequency refresh/render paths without breaking existing API contracts.

## Scope

- Optimize backend `collect_loop()` to reduce end-to-end cycle latency.
- Remove SQLite N+1 patterns in process tracking and alert persistence.
- Reduce replay frame generation complexity for large time windows.
- Reduce repeated agent-side blocking/system scans.
- Change frontend refresh behavior to load only the active tab workload.
- Reduce repeated frontend list/chart recomputation.

## Non-Goals

- No protocol redesign.
- No silent caching that hides stale failures.
- No removal of current REST endpoints or WebSocket message shape.
- No architectural migration to a streaming-only model.

## Backend Collection Path

`collect_loop()` remains the source of truth and keeps the current interval, but the three upstream agent reads must execute concurrently:

- `get_all_gpus()`
- `get_system_info()`
- `get_processes()`

The loop still persists snapshots, tracks processes, evaluates alerts, runs the scheduler, and broadcasts a realtime packet, but expensive sub-steps must avoid unnecessary per-item transactions or sequential waits.

## Agent-Side Sampling

System monitoring must stop using blocking CPU sampling on every request. The agent should warm up CPU counters once during startup and then use non-blocking reads during request handling.

Process discovery should use a short TTL snapshot cache for the shared “GPU process list” workload so that monitor/user/training endpoints can reuse the same scan result within a small window instead of repeating NVML + psutil enumeration multiple times per refresh burst.

## SQLite Optimizations

`track_processes()` must switch from per-process lookup/update to:

1. load active process rows once
2. compute inserts/updates/inactive rows in memory
3. execute batched `executemany` updates/inserts
4. commit once

Alert persistence must support batch insert so one collect cycle performs at most one alert transaction.

## Replay Frame Generation

`get_replay_frames()` must replace per-process bucket walking with a difference-event model:

- add `+1` at the first active bucket
- add `-1` after the last active bucket
- compute prefix sums across ordered buckets

This reduces the active-task portion from process-count × bucket-count behavior to event-count + bucket-count behavior.

## WebSocket Broadcast

Realtime broadcast should serialize once per payload and dispatch sends concurrently across active connections. Slow or broken sockets must not serialize the entire fan-out path.

## Frontend Refresh Strategy

`MonitorCenter.vue` must refresh only the active tab’s data set on its interval:

- system tab -> system detail
- training tab -> training logs
- users tab -> user stats
- timeline tab -> task history

Tab switches trigger an immediate load for the new tab. No background refresh should continue for inactive tabs.

## Frontend Compute Reduction

- `TaskManager.vue` should derive a normalized process list once, then derive filtered views and counters from that shared result.
- `PowerTrendChart.vue` should update chart data when GPU input changes instead of rebuilding the entire chart option on a separate timer.
- `GpuDetail.vue` should preprocess history arrays once per history payload instead of repeatedly mapping the same source array for each series.

## Validation

Tests should cover:

- backend collect loop concurrent agent reads
- batched process tracking and alert inserts
- replay frame correctness under large bucket spans
- monitor page active-tab-only refresh
- chart/list computation behavior regressions where feasible
