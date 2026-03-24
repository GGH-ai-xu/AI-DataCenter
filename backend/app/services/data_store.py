"""SQLite历史数据存储 - 异步读写GPU历史指标和告警"""

import os
import time
import logging
from typing import Optional

import aiosqlite

logger = logging.getLogger(__name__)

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
    timestamp REAL NOT NULL
);
"""


class DataStore:
    """异步SQLite数据存储"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._db: Optional[aiosqlite.Connection] = None

    async def init(self):
        """初始化数据库连接和表"""
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(_INIT_SQL)
        await self._db.commit()
        logger.info(f"数据库初始化完成: {self.db_path}")

    async def close(self):
        if self._db:
            await self._db.close()

    # ========== GPU历史数据 ==========

    async def save_gpu_snapshot(self, gpus: list[dict]):
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

    async def get_all_gpu_latest(self) -> list[dict]:
        """获取每张GPU最新的记录"""
        cursor = await self._db.execute(
            """SELECT * FROM gpu_history
               WHERE id IN (
                   SELECT MAX(id) FROM gpu_history GROUP BY gpu_index
               )
               ORDER BY gpu_index"""
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_power_summary(self, hours: float = 24.0) -> dict:
        """获取功耗统计摘要"""
        since = time.time() - hours * 3600
        cursor = await self._db.execute(
            """SELECT gpu_index,
                      AVG(power_usage) as avg_power,
                      MAX(power_usage) as max_power,
                      MIN(power_usage) as min_power,
                      COUNT(*) as samples
               FROM gpu_history
               WHERE timestamp >= ?
               GROUP BY gpu_index""",
            (since,),
        )
        rows = await cursor.fetchall()
        return {
            "hours": hours,
            "gpus": [dict(row) for row in rows],
            "total_avg_power": sum(dict(r)["avg_power"] for r in rows) if rows else 0,
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

    async def get_alerts(self, limit: int = 100, unack_only: bool = False) -> list[dict]:
        """获取告警列表"""
        where = "WHERE acknowledged = 0" if unack_only else ""
        cursor = await self._db.execute(
            f"SELECT * FROM alerts {where} ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

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

    # ========== 调度日志 ==========

    async def save_schedule_log(self, action: str, target: str, reason: str, result: str = ""):
        await self._db.execute(
            """INSERT INTO schedule_log (action, target, reason, result, timestamp)
               VALUES (?, ?, ?, ?, ?)""",
            (action, target, reason, result, time.time()),
        )
        await self._db.commit()
