from __future__ import annotations


def _catalog_item(definition) -> dict:
    manual = definition.manual_control
    return {
        "name": definition.name,
        "domain": definition.domain,
        "label": manual.label or definition.name,
        "description": manual.description,
        "risk_level": manual.risk_level,
        "permission_mode": manual.approval_policy,
        "required_role": manual.required_role,
        "requires_scope": definition.requires_scope,
        "side_effect_level": definition.side_effect_level,
    }


def list_manual_capabilities(registry) -> list[dict]:
    items = []
    for _, registered in registry.items():
        if not registered.definition.manual_control.enabled:
            continue
        items.append(_catalog_item(registered.definition))
    return sorted(items, key=lambda item: (item["domain"], item["label"], item["name"]))


def group_capabilities_by_domain(items: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    for item in items:
        grouped.setdefault(item["domain"], []).append(item)
    return [
        {"domain": domain, "capabilities": grouped[domain]}
        for domain in sorted(grouped)
    ]
