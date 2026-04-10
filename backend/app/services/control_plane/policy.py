from __future__ import annotations

from dataclasses import dataclass


ROLE_ORDER = {
    "observer": 0,
    "member": 1,
    "admin": 2,
}


@dataclass(frozen=True)
class ResolvedControlPolicy:
    required_role: str
    risk_level: str
    permission_mode: str


def _role_rank(role: str) -> int:
    return ROLE_ORDER.get(role or "", -1)


def ensure_manual_access(definition, user: dict) -> ResolvedControlPolicy:
    manual = definition.manual_control
    if not manual.enabled:
        raise LookupError("capability is not available for manual control")
    user_role = str(user.get("role") or "")
    if _role_rank(user_role) < _role_rank(manual.required_role):
        raise PermissionError("当前身份无权执行该能力")
    return ResolvedControlPolicy(
        required_role=manual.required_role,
        risk_level=manual.risk_level,
        permission_mode=manual.approval_policy,
    )


def ensure_confirmation(policy: ResolvedControlPolicy, request) -> None:
    if policy.permission_mode != "confirm_required":
        return
    if not request.acknowledge_risk:
        raise ValueError("真实执行前请先确认风险")
