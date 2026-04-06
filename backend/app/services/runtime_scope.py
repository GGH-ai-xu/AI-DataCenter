from __future__ import annotations


def build_realtime_scope(
    import_context,
    privacy,
    system: dict | None,
    gpus: list[dict] | None,
    processes: list[dict] | None,
) -> dict:
    scoped_gpus = import_context.filter_gpus(gpus or [])
    scoped_processes = import_context.filter_processes(processes or [])
    return {
        "system": system,
        "gpus": scoped_gpus,
        "processes": scoped_processes,
        "public_processes": privacy.sanitize_processes(scoped_processes),
    }
