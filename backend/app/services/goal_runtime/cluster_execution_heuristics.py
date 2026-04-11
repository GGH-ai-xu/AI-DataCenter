from __future__ import annotations


QUEUE_RECONCILE_KEYWORDS = (
    "队列调和",
    "调和队列",
    "queue reconcile",
    "reconcile queue",
    "推进等待作业",
)


def build_cluster_execution_actions(text: str) -> list[dict]:
    lowered = (text or "").lower()
    if not any(keyword in lowered for keyword in QUEUE_RECONCILE_KEYWORDS):
        return []
    return [
        {
            "action": "reconcile_queue",
            "target": {},
            "reason": "根据用户指令执行一次队列调和并推进等待作业",
        }
    ]
