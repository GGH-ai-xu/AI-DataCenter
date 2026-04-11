from __future__ import annotations

import json
from pathlib import Path

from report_book_charts_metrics import (
    agent_dimensions_svg,
    agent_effectiveness_svg,
    agent_integration_svg,
    api_domains_svg,
    capability_prefix_svg,
    command_lifecycle_svg,
    extension_status_svg,
    import_scope_svg,
    policy_linkage_svg,
    platform_scale_svg,
    scope_matrix_svg,
    test_domains_svg,
    validation_summary_svg,
)
from report_book_charts_experiments import (
    agent_experiment_svg,
    control_experiment_svg,
    history_experiment_svg,
    remote_budget_experiment_svg,
    remote_budget_timeline_svg,
    scope_experiment_svg,
)
from report_book_charts_structure import (
    agent_chain_svg,
    extension_map_svg,
    persistence_map_svg,
    problem_matrix_svg,
    system_panorama_svg,
    user_workflow_svg,
    workspace_map_svg,
)
from report_book_dataset import build_report_book_dataset


ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "assets"
DATA_DIR = ROOT / "data"


def main() -> None:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    data = build_report_book_dataset()
    (DATA_DIR / "report_book_metrics.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    charts = {
        "book_platform_scale.svg": platform_scale_svg(data),
        "book_system_panorama.svg": system_panorama_svg(data),
        "book_user_workflow.svg": user_workflow_svg(data),
        "book_problem_matrix.svg": problem_matrix_svg(data),
        "book_workspace_map.svg": workspace_map_svg(data),
        "book_persistence_map.svg": persistence_map_svg(data),
        "book_agent_chain.svg": agent_chain_svg(data),
        "book_extension_map.svg": extension_map_svg(data),
        "book_api_domains.svg": api_domains_svg(data),
        "book_capability_prefixes.svg": capability_prefix_svg(data),
        "book_validation_summary.svg": validation_summary_svg(data),
        "book_import_scope.svg": import_scope_svg(data),
        "book_scope_matrix.svg": scope_matrix_svg(data),
        "book_command_lifecycle.svg": command_lifecycle_svg(data),
        "book_policy_linkage.svg": policy_linkage_svg(data),
        "book_test_domains.svg": test_domains_svg(data),
        "book_agent_effectiveness.svg": agent_effectiveness_svg(data),
        "book_agent_integration.svg": agent_integration_svg(data),
        "book_agent_dimensions.svg": agent_dimensions_svg(data),
        "book_scope_experiment.svg": scope_experiment_svg(data),
        "book_history_experiment.svg": history_experiment_svg(data),
        "book_agent_experiment.svg": agent_experiment_svg(data),
        "book_control_experiment.svg": control_experiment_svg(data),
        "book_remote_budget_experiment.svg": remote_budget_experiment_svg(data),
        "book_remote_budget_timeline.svg": remote_budget_timeline_svg(data),
        "book_extension_status.svg": extension_status_svg(data),
    }
    for name, svg in charts.items():
        (ASSET_DIR / name).write_text(svg, encoding="utf-8")


if __name__ == "__main__":
    main()
