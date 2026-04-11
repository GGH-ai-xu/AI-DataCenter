from __future__ import annotations

import re


JOB_ID_PATTERN = re.compile(r"\b(job[-\w.]+)\b", flags=re.IGNORECASE)


def _find_job_ids(text: str) -> tuple[str, ...]:
    return tuple(match.group(1) for match in JOB_ID_PATTERN.finditer(text or ""))


def _requeue_keywords(text: str) -> bool:
    return any(word in text for word in ("重新排队", "重新入队", "重排作业", "requeue"))


def _preempt_keywords(text: str) -> bool:
    return any(word in text for word in ("抢占作业", "抢占", "preempt"))


def _checkpoint_keywords(text: str) -> bool:
    return any(word in text for word in ("检查点", "保存进度", "checkpoint"))


def _restore_keywords(text: str) -> bool:
    return (
        any(word in text for word in ("恢复检查点", "检查点恢复", "restore"))
        or ("恢复" in text and _checkpoint_keywords(text))
    )


def build_job_control_actions(text: str) -> list[dict]:
    lowered = (text or "").lower()
    job_ids = _find_job_ids(lowered)
    if not job_ids:
        return []
    actions: list[dict] = []
    if _requeue_keywords(lowered):
        actions.append(
            {
                "action": "requeue_job",
                "target": {"job_id": job_ids[0]},
                "reason": f"根据用户指令将作业 {job_ids[0]} 重新入队",
            }
        )
    if _preempt_keywords(lowered):
        index = 1 if len(job_ids) > 1 and actions else 0
        actions.append(
            {
                "action": "preempt_job",
                "target": {"job_id": job_ids[index]},
                "reason": f"根据用户指令抢占作业 {job_ids[index]}",
            }
        )
    if _checkpoint_keywords(lowered):
        actions.append(
            {
                "action": "checkpoint_job",
                "target": {"job_id": job_ids[0]},
                "reason": f"根据用户指令为作业 {job_ids[0]} 创建检查点",
            }
        )
    if _restore_keywords(lowered):
        actions.append(
            {
                "action": "restore_job",
                "target": {"job_id": job_ids[-1]},
                "reason": f"根据用户指令恢复作业 {job_ids[-1]}",
            }
        )
    return actions
