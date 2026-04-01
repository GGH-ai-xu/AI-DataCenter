from collections import defaultdict


MAX_SCHEDULE_ACTIONS = 4


def build_empty_frame(bucket_ts: int) -> dict:
    return {
        "bucket_ts": bucket_ts,
        "avg_power": 0.0,
        "avg_util": 0.0,
        "avg_memory_util": 0.0,
        "avg_power_limit": 0.0,
        "max_temp": 0,
        "gpu_count": 0,
        "alert_count": 0,
        "critical_alert_count": 0,
        "schedule_action_count": 0,
        "schedule_actions": [],
        "active_task_count": 0,
        "active_user_count": 0,
    }


def build_frame_index(
    start_bucket: int,
    end_bucket: int,
    bucket_seconds: int,
) -> dict[int, dict]:
    return {
        bucket_ts: build_empty_frame(bucket_ts)
        for bucket_ts in range(
            start_bucket,
            end_bucket + bucket_seconds,
            bucket_seconds,
        )
    }


def apply_gpu_rows(frames: dict[int, dict], rows: list[dict]):
    for item in rows:
        frame = frames.get(item["bucket_ts"])
        if frame is None:
            continue
        frame["avg_power"] = round(item.get("avg_power") or 0, 1)
        frame["avg_util"] = round(item.get("avg_util") or 0, 1)
        frame["avg_memory_util"] = round(item.get("avg_memory_util") or 0, 1)
        frame["avg_power_limit"] = round(item.get("avg_power_limit") or 0, 1)
        frame["max_temp"] = int(item.get("max_temp") or 0)
        frame["gpu_count"] = int(item.get("gpu_count") or 0)


def apply_alert_rows(frames: dict[int, dict], rows: list[dict]):
    for item in rows:
        frame = frames.get(item["bucket_ts"])
        if frame is None:
            continue
        frame["alert_count"] = int(item.get("alert_count") or 0)
        frame["critical_alert_count"] = int(
            item.get("critical_alert_count") or 0
        )


def apply_schedule_rows(
    frames: dict[int, dict],
    rows: list[dict],
    bucket_seconds: int,
    start_bucket: int,
):
    for item in rows:
        timestamp = item.get("timestamp") or start_bucket
        bucket_ts = int(timestamp // bucket_seconds) * bucket_seconds
        frame = frames.get(bucket_ts)
        if frame is None:
            continue
        frame["schedule_action_count"] += 1
        if len(frame["schedule_actions"]) >= MAX_SCHEDULE_ACTIONS:
            continue
        frame["schedule_actions"].append(
            {
                "action": item.get("action"),
                "reason": item.get("reason"),
                "result": item.get("result"),
            }
        )


def _bucket_floor(timestamp: float, bucket_seconds: int) -> int:
    return int(timestamp // bucket_seconds) * bucket_seconds


def _apply_interval_delta(
    deltas: dict[int, int],
    start_ts: float,
    end_ts: float,
    start_bucket: int,
    end_bucket: int,
    bucket_seconds: int,
):
    bucket_start = max(start_bucket, _bucket_floor(start_ts, bucket_seconds))
    bucket_end = min(end_bucket, _bucket_floor(end_ts, bucket_seconds))
    if bucket_end < bucket_start:
        return
    deltas[bucket_start] += 1
    after_end = bucket_end + bucket_seconds
    if after_end <= end_bucket:
        deltas[after_end] -= 1


def _merge_intervals(intervals: list[tuple[float, float]]) -> list[tuple[float, float]]:
    merged: list[list[float]] = []
    for start_ts, end_ts in sorted(intervals):
        if not merged or start_ts > merged[-1][1]:
            merged.append([start_ts, end_ts])
            continue
        merged[-1][1] = max(merged[-1][1], end_ts)
    return [(start_ts, end_ts) for start_ts, end_ts in merged]


def _flush_delta_series(
    frames: dict[int, dict],
    deltas: dict[int, int],
    field: str,
):
    running_total = 0
    for bucket_ts in sorted(frames):
        running_total += deltas.get(bucket_ts, 0)
        frames[bucket_ts][field] = running_total


def apply_process_rows(
    frames: dict[int, dict],
    rows: list[dict],
    start_bucket: int,
    end_bucket: int,
    bucket_seconds: int,
):
    task_deltas: dict[int, int] = defaultdict(int)
    user_deltas: dict[int, int] = defaultdict(int)
    user_intervals: dict[str, list[tuple[float, float]]] = defaultdict(list)

    for item in rows:
        start_ts = max(
            float(start_bucket),
            float(item.get("first_seen") or start_bucket),
        )
        end_ts = min(
            float(end_bucket),
            max(start_ts, float(item.get("last_seen") or start_ts)),
        )
        if end_ts < start_bucket:
            continue
        _apply_interval_delta(
            task_deltas,
            start_ts,
            end_ts,
            start_bucket,
            end_bucket,
            bucket_seconds,
        )
        username = str(item.get("username") or "unknown")
        user_intervals[username].append((start_ts, end_ts))

    for intervals in user_intervals.values():
        for start_ts, end_ts in _merge_intervals(intervals):
            _apply_interval_delta(
                user_deltas,
                start_ts,
                end_ts,
                start_bucket,
                end_bucket,
                bucket_seconds,
            )

    _flush_delta_series(frames, task_deltas, "active_task_count")
    _flush_delta_series(frames, user_deltas, "active_user_count")
