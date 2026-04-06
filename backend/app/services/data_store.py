"""SQLite历史数据存储 - 异步读写GPU历史指标和告警"""

import json
import logging
import os
import time
from typing import Optional

import aiosqlite
from app.services.process_history_sync import (
    build_process_batches,
    normalize_processes,
)
from app.services.replay_frames import (
    apply_alert_rows,
    apply_gpu_rows,
    apply_process_rows,
    apply_schedule_rows,
    build_frame_index,
)

logger = logging.getLogger(__name__)

SQLITE_CONNECTION_TIMEOUT_SECONDS = 30.0
SQLITE_BUSY_TIMEOUT_MS = 30000
SQLITE_SYNCHRONOUS_NORMAL = 1
EMPTY_SCOPE_JSON = "[]"

# 建表SQL
_INIT_SQL = """
CREATE TABLE IF NOT EXISTS gpu_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gpu_index INTEGER NOT NULL,
    temperature INTEGER,
    power_usage REAL,
    power_limit REAL,
    gpu_utilization INTEGER,
    memory_utilization INTEGER,
    memory_used INTEGER,
    memory_total INTEGER,
    fan_speed INTEGER,
    timestamp REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_gpu_history_ts ON gpu_history(timestamp);
CREATE INDEX IF NOT EXISTS idx_gpu_history_gpu_ts ON gpu_history(gpu_index, timestamp);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gpu_index INTEGER NOT NULL,
    alert_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    message TEXT NOT NULL,
    value REAL,
    threshold REAL,
    timestamp REAL NOT NULL,
    acknowledged INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_alerts_ts ON alerts(timestamp);

CREATE TABLE IF NOT EXISTS task_priorities (
    pid INTEGER PRIMARY KEY,
    priority TEXT NOT NULL DEFAULT 'normal',
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS schedule_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL,
    target TEXT NOT NULL,
    reason TEXT NOT NULL,
    result TEXT,
    scope_gpu_indexes_json TEXT NOT NULL DEFAULT '[]',
    timestamp REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS process_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pid INTEGER NOT NULL,
    gpu_index INTEGER NOT NULL,
    username TEXT,
    command TEXT,
    gpu_memory_used INTEGER,
    first_seen REAL NOT NULL,
    last_seen REAL NOT NULL,
    is_active INTEGER DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_process_history_active ON process_history(is_active);
CREATE INDEX IF NOT EXISTS idx_process_history_ts ON process_history(last_seen);

CREATE TABLE IF NOT EXISTS optimization_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    baseline_power REAL,
    optimized_power REAL,
    saving_pct REAL,
    co2_saved_kg REAL,
    actions_json TEXT,
    scope_gpu_indexes_json TEXT NOT NULL DEFAULT '[]',
    timestamp REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_opt_snap_ts ON optimization_snapshots(timestamp);

CREATE TABLE IF NOT EXISTS user_governance_rules (
    username TEXT PRIMARY KEY,
    role TEXT NOT NULL DEFAULT 'member',
    max_tasks INTEGER NOT NULL DEFAULT 4,
    max_gpu_count INTEGER NOT NULL DEFAULT 1,
    max_memory_gb REAL NOT NULL DEFAULT 8,
    allow_preempt INTEGER NOT NULL DEFAULT 1,
    note TEXT DEFAULT '',
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS governance_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL,
    target TEXT NOT NULL,
    reason TEXT DEFAULT '',
    operator TEXT DEFAULT 'user',
    source TEXT DEFAULT 'manual',
    dry_run INTEGER DEFAULT 0,
    success INTEGER DEFAULT 1,
    error_message TEXT DEFAULT '',
    risk_level TEXT DEFAULT 'low',
    detail TEXT DEFAULT '',
    timestamp REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_ts ON governance_audit_log(timestamp);
"""


class DataStore:
    """异步SQLite数据存储"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._db: Optional[aiosqlite.Connection] = None

    async def _configure_sqlite(self):
        if not self._db:
            return
        await self._db.execute("PRAGMA journal_mode=WAL;")
        await self._db.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS};")
        await self._db.execute(f"PRAGMA synchronous={SQLITE_SYNCHRONOUS_NORMAL};")

    async def init(self):
        """初始化数据库连接和表"""
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        self._db = await aiosqlite.connect(
            self.db_path,
            timeout=SQLITE_CONNECTION_TIMEOUT_SECONDS,
        )
        self._db.row_factory = aiosqlite.Row
        await self._configure_sqlite()
        await self._db.executescript(_INIT_SQL)
        await self._ensure_scope_columns()
        await self._db.commit()
        logger.info(f"数据库初始化完成: {self.db_path}")

    async def close(self):
        if self._db:
            await self._db.close()

    async def _ensure_scope_columns(self):
        if not self._db:
            return
        statements = (
            "ALTER TABLE schedule_log ADD COLUMN scope_gpu_indexes_json TEXT NOT NULL DEFAULT '[]'",
            "ALTER TABLE optimization_snapshots ADD COLUMN scope_gpu_indexes_json TEXT NOT NULL DEFAULT '[]'",
        )
        for statement in statements:
            try:
                await self._db.execute(statement)
            except aiosqlite.OperationalError:
                continue

    @staticmethod
    def _normalize_gpu_indexes(gpu_indexes: list[int] | None) -> list[int] | None:
        if gpu_indexes is None:
            return None
        return sorted({int(item) for item in gpu_indexes})

    @classmethod
    def _scope_json(cls, gpu_indexes: list[int] | None) -> str:
        normalized = cls._normalize_gpu_indexes(gpu_indexes)
        if normalized is None:
            return EMPTY_SCOPE_JSON
        return json.dumps(normalized, ensure_ascii=False)

    @classmethod
    def _gpu_where_clause(
        cls,
        column: str,
        gpu_indexes: list[int] | None,
        prefix: str = "AND",
    ) -> tuple[str, tuple]:
        normalized = cls._normalize_gpu_indexes(gpu_indexes)
        if normalized is None:
            return "", ()
        if not normalized:
            return f" {prefix} 1 = 0", ()
        placeholders = ",".join("?" for _ in normalized)
        return f" {prefix} {column} IN ({placeholders})", tuple(normalized)

    @classmethod
    def _scope_where_clause(
        cls,
        column: str,
        gpu_indexes: list[int] | None,
        prefix: str = "AND",
    ) -> tuple[str, tuple]:
        normalized = cls._normalize_gpu_indexes(gpu_indexes)
        if normalized is None:
            return "", ()
        if not normalized:
            return f" {prefix} 1 = 0", ()
        return f" {prefix} {column} = ?", (cls._scope_json(normalized),)

    # ========== GPU历史数据 ==========

    async def save_gpu_snapshot(self, gpus: list[dict], commit: bool = True):
        """批量保存GPU快照"""
        if not self._db or not gpus:
            return
        rows = [
            (
                g["index"], g["temperature"], g["power_usage"], g["power_limit"],
                g["gpu_utilization"], g["memory_utilization"],
                g["memory_used"], g["memory_total"], g["fan_speed"], g["timestamp"],
            )
            for g in gpus
        ]
        await self._db.executemany(
            """INSERT INTO gpu_history
               (gpu_index, temperature, power_usage, power_limit,
                gpu_utilization, memory_utilization, memory_used, memory_total,
                fan_speed, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
        if commit:
            await self._db.commit()

    async def get_gpu_history(
        self, gpu_index: int, hours: float = 1.0, limit: int = 3600
    ) -> list[dict]:
        """查询指定GPU的历史数据"""
        since = time.time() - hours * 3600
        cursor = await self._db.execute(
            """SELECT * FROM gpu_history
               WHERE gpu_index = ? AND timestamp >= ?
               ORDER BY timestamp ASC LIMIT ?""",
            (gpu_index, since, limit),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_all_gpu_latest(
        self,
        gpu_indexes: list[int] | None = None,
    ) -> list[dict]:
        """获取每张GPU最新的记录"""
        where, params = self._gpu_where_clause("gpu_index", gpu_indexes)
        cursor = await self._db.execute(
            """SELECT * FROM gpu_history
               WHERE id IN (
                   SELECT MAX(id) FROM gpu_history GROUP BY gpu_index
               )
            """
            + where
            + """
               ORDER BY gpu_index""",
            params,
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_power_summary(
        self,
        hours: float = 24.0,
        gpu_indexes: list[int] | None = None,
    ) -> dict:
        """获取功耗统计摘要"""
        since = time.time() - hours * 3600
        where, scope_params = self._gpu_where_clause("gpu_index", gpu_indexes)
        cursor = await self._db.execute(
            """SELECT gpu_index,
                      AVG(power_usage) as avg_power,
                      MAX(power_usage) as max_power,
                      MIN(power_usage) as min_power,
                      COUNT(*) as samples
               FROM gpu_history
               WHERE timestamp >= ?
            """
            + where
            + """
               GROUP BY gpu_index""",
            (since, *scope_params),
        )
        rows = await cursor.fetchall()
        return {
            "hours": hours,
            "gpus": [dict(row) for row in rows],
            "total_avg_power": sum(float(row["avg_power"] or 0) for row in rows),
        }

    async def cleanup_old_data(self, days: int = 7):
        """清理过期历史数据"""
        cutoff = time.time() - days * 86400
        await self._db.execute(
            "DELETE FROM gpu_history WHERE timestamp < ?", (cutoff,)
        )
        await self._db.commit()

    # ========== 告警 ==========

    async def save_alert(self, alert: dict) -> int:
        """保存告警记录"""
        cursor = await self._db.execute(
            """INSERT INTO alerts (gpu_index, alert_type, severity, message, value, threshold, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                alert["gpu_index"], alert["alert_type"], alert["severity"],
                alert["message"], alert["value"], alert["threshold"],
                alert["timestamp"],
            ),
        )
        await self._db.commit()
        return cursor.lastrowid

    async def save_alerts(self, alerts: list[dict], commit: bool = True):
        """批量保存告警记录"""
        if not self._db or not alerts:
            return
        rows = [
            (
                alert["gpu_index"],
                alert["alert_type"],
                alert["severity"],
                alert["message"],
                alert["value"],
                alert["threshold"],
                alert["timestamp"],
            )
            for alert in alerts
        ]
        await self._db.executemany(
            """INSERT INTO alerts
               (gpu_index, alert_type, severity, message, value, threshold, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
        if commit:
            await self._db.commit()

    async def get_alerts(
        self,
        limit: int = 100,
        unack_only: bool = False,
        gpu_indexes: list[int] | None = None,
    ) -> list[dict]:
        """获取告警列表"""
        where = "WHERE acknowledged = 0" if unack_only else ""
        prefix = "AND" if where else "WHERE"
        scope_where, scope_params = self._gpu_where_clause(
            "gpu_index",
            gpu_indexes,
            prefix=prefix,
        )
        cursor = await self._db.execute(
            f"SELECT * FROM alerts {where}{scope_where} ORDER BY timestamp DESC LIMIT ?",
            (*scope_params, limit),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_alert_by_id(self, alert_id: int) -> dict | None:
        """按 ID 读取单条告警。"""
        cursor = await self._db.execute(
            "SELECT * FROM alerts WHERE id = ?",
            (alert_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def acknowledge_alert(self, alert_id: int):
        """确认告警"""
        await self._db.execute(
            "UPDATE alerts SET acknowledged = 1 WHERE id = ?", (alert_id,)
        )
        await self._db.commit()

    # ========== 任务优先级 ==========

    async def set_task_priority(self, pid: int, priority: str):
        """设置任务优先级"""
        await self._db.execute(
            """INSERT OR REPLACE INTO task_priorities (pid, priority, updated_at)
               VALUES (?, ?, ?)""",
            (pid, priority, time.time()),
        )
        await self._db.commit()

    async def get_task_priority(self, pid: int) -> str:
        cursor = await self._db.execute(
            "SELECT priority FROM task_priorities WHERE pid = ?", (pid,)
        )
        row = await cursor.fetchone()
        return dict(row)["priority"] if row else "normal"

    async def get_all_task_priorities(self) -> dict[int, str]:
        cursor = await self._db.execute("SELECT pid, priority FROM task_priorities")
        rows = await cursor.fetchall()
        return {row["pid"]: row["priority"] for row in rows}

    async def upsert_user_governance_rule(
        self,
        username: str,
        role: str,
        max_tasks: int,
        max_gpu_count: int,
        max_memory_gb: float,
        allow_preempt: bool,
        note: str = "",
    ):
        """新增或更新用户治理规则"""
        await self._db.execute(
            """INSERT OR REPLACE INTO user_governance_rules
               (username, role, max_tasks, max_gpu_count, max_memory_gb, allow_preempt, note, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                username,
                role,
                max_tasks,
                max_gpu_count,
                max_memory_gb,
                1 if allow_preempt else 0,
                note,
                time.time(),
            ),
        )
        await self._db.commit()

    async def get_user_governance_rules(self) -> dict[str, dict]:
        """获取全部用户治理规则"""
        cursor = await self._db.execute(
            """SELECT username, role, max_tasks, max_gpu_count, max_memory_gb, allow_preempt, note, updated_at
               FROM user_governance_rules
               ORDER BY updated_at DESC"""
        )
        rows = await cursor.fetchall()
        data = {}
        for row in rows:
            item = dict(row)
            item["allow_preempt"] = bool(item.get("allow_preempt", 1))
            data[item["username"]] = item
        return data

    async def get_known_usernames(self) -> list[str]:
        """收集已出现过的用户名，用于脱敏别名反解。"""
        cursor = await self._db.execute(
            """SELECT DISTINCT username
               FROM (
                   SELECT username FROM user_governance_rules
                   UNION ALL
                   SELECT username FROM process_history
               )
               WHERE username IS NOT NULL
                 AND TRIM(username) != ''
               ORDER BY username"""
        )
        rows = await cursor.fetchall()
        return [row["username"] for row in rows]

    async def delete_user_governance_rule(self, username: str):
        """删除单个用户治理规则，恢复为平台默认阈值"""
        await self._db.execute(
            "DELETE FROM user_governance_rules WHERE username = ?",
            (username,),
        )
        await self._db.commit()

    # ========== 治理审计日志 ==========

    async def save_audit_log(
        self,
        action: str,
        target: str,
        reason: str = '',
        operator: str = 'user',
        source: str = 'manual',
        success: bool = True,
        error_message: str = '',
        risk_level: str = 'low',
        detail: str = '',
    ):
        """写入治理操作审计记录"""
        if not self._db:
            return
        await self._db.execute(
            """INSERT INTO governance_audit_log
               (action, target, reason, operator, source, dry_run, success, error_message, risk_level, detail, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                action, target, reason, operator, source,
                0,
                1 if success else 0,
                error_message, risk_level, detail, time.time(),
            ),
        )
        await self._db.commit()

    async def get_audit_logs(self, limit: int = 100, hours: float = 72) -> list[dict]:
        """读取近N小时的治理审计日志，按时间倒序"""
        since = time.time() - hours * 3600
        cursor = await self._db.execute(
            """SELECT * FROM governance_audit_log
               WHERE timestamp >= ?
               ORDER BY timestamp DESC LIMIT ?""",
            (since, limit),
        )
        rows = await cursor.fetchall()
        return [
            {key: value for key, value in dict(row).items() if key != "dry_run"}
            for row in rows
        ]

    async def save_governance_audit(self, action: str, target: str, reason: str, result: str, operator: str = "user"):
        """记录治理审计日志（写入 schedule_log 表）"""
        if not self._db:
            return
        await self._db.execute(
            "INSERT INTO schedule_log (action, target, reason, result, timestamp) VALUES (?, ?, ?, ?, ?)",
            (action, target, reason, f"{operator}|{result}", time.time()),
        )
        await self._db.commit()

    async def get_governance_audit_log(self, limit: int = 100) -> list[dict]:
        """获取治理审计日志（从 schedule_log 表解析）"""
        if not self._db:
            return []
        cursor = await self._db.execute(
            "SELECT id, action, target, reason, result, timestamp FROM schedule_log ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        rows = await cursor.fetchall()
        logs = []
        for row in rows:
            result_str = row["result"] or ""
            parts = result_str.split("|")
            operator = "system"
            status = parts[-1] if parts else "unknown"
            if len(parts) >= 2:
                operator = parts[-2]
            logs.append({
                "id": row["id"],
                "action": row["action"],
                "target": row["target"],
                "reason": row["reason"],
                "operator": operator,
                "status": status,
                "timestamp": row["timestamp"],
            })
        return logs

    # ========== 调度日志 ==========

    async def save_schedule_log(
        self,
        action: str,
        target: str,
        reason: str,
        result: str = "",
        gpu_indexes: list[int] | None = None,
    ):
        await self._db.execute(
            """INSERT INTO schedule_log
               (action, target, reason, result, scope_gpu_indexes_json, timestamp)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                action,
                target,
                reason,
                result,
                self._scope_json(gpu_indexes),
                time.time(),
            ),
        )
        await self._db.commit()

    # ========== 进程历史 ==========

    async def track_processes(
        self,
        processes: list[dict],
        timestamp: float | None = None,
        commit: bool = True,
    ):
        """追踪进程生命周期：新进程记录first_seen，已有进程更新last_seen，消失进程标为inactive"""
        if not self._db:
            return

        now = time.time() if timestamp is None else timestamp
        normalized_processes = normalize_processes(processes)
        if not normalized_processes:
            await self._db.execute(
                "UPDATE process_history SET is_active = 0, last_seen = ? WHERE is_active = 1",
                (now,),
            )
            if commit:
                await self._db.commit()
            return

        cursor = await self._db.execute(
            "SELECT id, pid FROM process_history WHERE is_active = 1"
        )
        active_rows = {
            int(row["pid"]): int(row["id"])
            for row in await cursor.fetchall()
        }
        updates, inserts, stale_ids = build_process_batches(
            normalized_processes,
            active_rows,
            now,
        )

        if updates:
            await self._db.executemany(
                """UPDATE process_history
                   SET last_seen = ?, gpu_index = ?, username = ?, command = ?, gpu_memory_used = ?
                   WHERE id = ?""",
                updates,
            )
        if inserts:
            await self._db.executemany(
                """INSERT INTO process_history
                   (pid, gpu_index, username, command, gpu_memory_used, first_seen, last_seen, is_active)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 1)""",
                inserts,
            )
        if stale_ids:
            placeholders = ",".join("?" for _ in stale_ids)
            await self._db.execute(
                f"UPDATE process_history SET is_active = 0, last_seen = ? WHERE id IN ({placeholders})",
                (now, *stale_ids),
            )

        if commit:
            await self._db.commit()

    async def save_collection_cycle(
        self,
        gpus: list[dict],
        processes: list[dict],
        alerts: list[dict],
    ):
        """以单事务写入一轮采集结果，避免热路径频繁提交。"""
        if not self._db:
            return
        try:
            await self.save_gpu_snapshot(gpus, commit=False)
            await self.track_processes(processes, commit=False)
            await self.save_alerts(alerts, commit=False)
        except Exception:
            await self._db.rollback()
            raise
        await self._db.commit()

    async def get_process_timeline(
        self,
        hours: float = 24.0,
        gpu_indexes: list[int] | None = None,
    ) -> list[dict]:
        """获取进程历史时间线"""
        since = time.time() - hours * 3600
        where, scope_params = self._gpu_where_clause("gpu_index", gpu_indexes)
        cursor = await self._db.execute(
            """SELECT * FROM process_history
               WHERE last_seen >= ?
            """
            + where
            + """
               ORDER BY first_seen DESC""",
            (since, *scope_params),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    # ========== 能耗分析 ==========

    async def get_hourly_power_aggregation(
        self,
        hours: float = 24.0,
        gpu_indexes: list[int] | None = None,
    ) -> list[dict]:
        """按小时聚合功耗数据，用于时段分析和预测基础"""
        since = time.time() - hours * 3600
        where, scope_params = self._gpu_where_clause("gpu_index", gpu_indexes)
        cursor = await self._db.execute(
            """SELECT
                   CAST(strftime('%H', datetime(timestamp, 'unixepoch', 'localtime')) AS INTEGER) as hour,
                   AVG(power_usage) as avg_power,
                   MAX(power_usage) as max_power,
                   MIN(power_usage) as min_power,
                   SUM(power_usage) as total_power,
                   COUNT(*) as samples,
                   AVG(gpu_utilization) as avg_util,
                   AVG(temperature) as avg_temp
               FROM gpu_history
               WHERE timestamp >= ?
            """
            + where
            + """
               GROUP BY hour
               ORDER BY hour""",
            (since, *scope_params),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def save_optimization_snapshot(
        self,
        data: dict,
        gpu_indexes: list[int] | None = None,
    ):
        """保存优化操作快照"""
        scope_indexes = (
            gpu_indexes
            if gpu_indexes is not None
            else data.get("scope_gpu_indexes")
        )
        await self._db.execute(
            """INSERT INTO optimization_snapshots
               (baseline_power, optimized_power, saving_pct, co2_saved_kg, actions_json, scope_gpu_indexes_json, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                data.get("baseline_power", 0),
                data.get("optimized_power", 0),
                data.get("saving_pct", 0),
                data.get("co2_saved_kg", 0),
                data.get("actions_json", "[]"),
                self._scope_json(scope_indexes),
                time.time(),
            ),
        )
        await self._db.commit()

    async def cleanup_untrusted_optimization_history(self) -> int:
        """清理明显不可信的优化快照，避免旧错误分析污染历史视图"""
        cursor = await self._db.execute(
            """DELETE FROM optimization_snapshots
               WHERE COALESCE(baseline_power, 0) < 0
                  OR COALESCE(optimized_power, 0) < 0
                  OR COALESCE(optimized_power, 0) > COALESCE(baseline_power, 0)
                  OR COALESCE(saving_pct, 0) < 0
                  OR COALESCE(saving_pct, 0) > 100
                  OR (
                        COALESCE(baseline_power, 0) < 30
                    AND COALESCE(saving_pct, 0) > 0
                  )"""
        )
        await self._db.commit()
        return cursor.rowcount or 0

    async def get_optimization_history(
        self,
        hours: float = 72.0,
        gpu_indexes: list[int] | None = None,
    ) -> list[dict]:
        """查询优化历史快照"""
        since = time.time() - hours * 3600
        where, scope_params = self._scope_where_clause(
            "scope_gpu_indexes_json",
            gpu_indexes,
        )
        cursor = await self._db.execute(
            """SELECT * FROM optimization_snapshots
               WHERE timestamp >= ?
                 AND COALESCE(baseline_power, 0) >= 0
                 AND COALESCE(optimized_power, 0) >= 0
                 AND COALESCE(optimized_power, 0) <= COALESCE(baseline_power, 0)
                 AND COALESCE(saving_pct, 0) >= 0
                 AND COALESCE(saving_pct, 0) <= 100
                 AND NOT (
                        COALESCE(baseline_power, 0) < 30
                    AND COALESCE(saving_pct, 0) > 0
                 )
            """
            + where
            + """
               ORDER BY timestamp DESC LIMIT 50""",
            (since, *scope_params),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_schedule_history(
        self,
        hours: float = 72.0,
        limit: int = 50,
        gpu_indexes: list[int] | None = None,
    ) -> list[dict]:
        """获取调度历史日志"""
        since = time.time() - hours * 3600
        where, scope_params = self._scope_where_clause(
            "scope_gpu_indexes_json",
            gpu_indexes,
        )
        cursor = await self._db.execute(
            """SELECT * FROM schedule_log
               WHERE timestamp >= ?
            """
            + where
            + """
               ORDER BY timestamp DESC LIMIT ?""",
            (since, *scope_params, limit),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_hourly_power_series(
        self,
        hours: float = 72.0,
        gpu_indexes: list[int] | None = None,
    ) -> list[dict]:
        """按小时聚合功耗时间序列（含时间戳），用于历史对比"""
        since = time.time() - hours * 3600
        where, scope_params = self._gpu_where_clause("gpu_index", gpu_indexes)
        cursor = await self._db.execute(
            """SELECT
                   CAST((timestamp / 3600) AS INTEGER) * 3600 as hour_ts,
                   AVG(power_usage) as avg_power,
                   MAX(power_usage) as max_power,
                   MIN(power_usage) as min_power,
                   COUNT(*) as samples
               FROM gpu_history
               WHERE timestamp >= ?
            """
            + where
            + """
               GROUP BY hour_ts
               ORDER BY hour_ts""",
            (since, *scope_params),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_user_stats(
        self,
        gpu_indexes: list[int] | None = None,
    ) -> list[dict]:
        """按用户统计当前资源占用"""
        where, scope_params = self._gpu_where_clause(
            "gpu_index",
            gpu_indexes,
            prefix="AND",
        )
        cursor = await self._db.execute(
            """SELECT username,
                      COUNT(DISTINCT pid) as task_count,
                      COUNT(DISTINCT gpu_index) as gpu_count,
                      SUM(gpu_memory_used) as total_memory,
                      MIN(first_seen) as earliest_start,
                      MAX(last_seen) as latest_activity
               FROM process_history
               WHERE is_active = 1
            """
            + where
            + """
               GROUP BY username
               ORDER BY total_memory DESC"""
            ,
            scope_params,
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_replay_frames(
        self,
        hours: float = 24.0,
        bucket_minutes: int = 10,
        gpu_indexes: list[int] | None = None,
    ) -> list[dict]:
        """构建治理回放帧，按时间桶复盘功率、告警与调度动作。"""
        if not self._db:
            return []

        bucket_seconds = max(60, int(bucket_minutes) * 60)
        now = time.time()
        since = now - hours * 3600
        start_bucket = int(since // bucket_seconds) * bucket_seconds
        end_bucket = int(now // bucket_seconds) * bucket_seconds
        frames = build_frame_index(start_bucket, end_bucket, bucket_seconds)
        gpu_where, gpu_params = self._gpu_where_clause("gpu_index", gpu_indexes)
        process_where, process_params = self._gpu_where_clause(
            "gpu_index",
            gpu_indexes,
        )
        scope_where, scope_params = self._scope_where_clause(
            "scope_gpu_indexes_json",
            gpu_indexes,
        )

        gpu_rows = await self._fetch_rows(
            """SELECT CAST(timestamp / ? AS INTEGER) * ? AS bucket_ts,
                      AVG(power_usage) AS avg_power,
                      AVG(gpu_utilization) AS avg_util,
                      AVG(memory_utilization) AS avg_memory_util,
                      AVG(power_limit) AS avg_power_limit,
                      MAX(temperature) AS max_temp,
                      COUNT(DISTINCT gpu_index) AS gpu_count
               FROM gpu_history
               WHERE timestamp >= ?
            """
            + gpu_where
            + """
               GROUP BY bucket_ts
               ORDER BY bucket_ts""",
            (bucket_seconds, bucket_seconds, since, *gpu_params),
        )
        apply_gpu_rows(frames, gpu_rows)

        alert_rows = await self._fetch_rows(
            """SELECT CAST(timestamp / ? AS INTEGER) * ? AS bucket_ts,
                      COUNT(*) AS alert_count,
                      SUM(CASE WHEN severity = 'critical' THEN 1 ELSE 0 END) AS critical_alert_count
               FROM alerts
               WHERE timestamp >= ?
            """
            + gpu_where
            + """
               GROUP BY bucket_ts
               ORDER BY bucket_ts""",
            (bucket_seconds, bucket_seconds, since, *gpu_params),
        )
        apply_alert_rows(frames, alert_rows)

        schedule_rows = await self._fetch_rows(
            """SELECT action, reason, result, timestamp
               FROM schedule_log
               WHERE timestamp >= ?
            """
            + scope_where
            + """
               ORDER BY timestamp ASC""",
            (since, *scope_params),
        )
        apply_schedule_rows(frames, schedule_rows, bucket_seconds, start_bucket)

        process_rows = await self._fetch_rows(
            """SELECT username, first_seen, last_seen
               FROM process_history
               WHERE last_seen >= ?
            """
            + process_where
            + """
               ORDER BY first_seen ASC""",
            (since, *process_params),
        )
        apply_process_rows(
            frames,
            process_rows,
            start_bucket,
            end_bucket,
            bucket_seconds,
        )
        return [frames[bucket_ts] for bucket_ts in sorted(frames)]

    async def _fetch_rows(self, query: str, params: tuple) -> list[dict]:
        cursor = await self._db.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_data_statistics(self) -> dict:
        """聚合各表记录数、采集时间范围与吞吐率，用于展示大数据处理规模"""
        if not self._db:
            return {"total_records": 0, "tables": {}, "collection_start": None,
                    "collection_duration_hours": 0, "avg_records_per_hour": 0}

        tables = {
            "gpu_history": "GPU 功耗快照",
            "process_history": "进程追踪记录",
            "alerts": "告警事件",
            "schedule_log": "调度动作日志",
            "optimization_snapshots": "优化快照",
            "governance_audit_log": "治理审计日志",
        }
        counts = {}
        total = 0
        for table_name, label in tables.items():
            cursor = await self._db.execute(f"SELECT COUNT(*) AS cnt FROM {table_name}")
            row = await cursor.fetchone()
            cnt = row["cnt"] if row else 0
            counts[table_name] = {"label": label, "count": cnt}
            total += cnt

        # 采集起始时间: gpu_history 中最早的 timestamp
        cursor = await self._db.execute(
            "SELECT MIN(timestamp) AS earliest FROM gpu_history"
        )
        row = await cursor.fetchone()
        earliest = row["earliest"] if row else None
        now = time.time()
        duration_hours = (now - earliest) / 3600 if earliest else 0
        avg_per_hour = total / duration_hours if duration_hours > 0 else 0

        return {
            "total_records": total,
            "tables": counts,
            "collection_start": earliest,
            "collection_duration_hours": round(duration_hours, 1),
            "avg_records_per_hour": round(avg_per_hour, 1),
        }
