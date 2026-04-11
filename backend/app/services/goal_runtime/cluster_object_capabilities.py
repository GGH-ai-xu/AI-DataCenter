from __future__ import annotations

from app.api.cluster_jobs import sync_cluster_nodes
from app.services.goal_runtime.capability import CapabilityDefinition


def register_cluster_object_capabilities(
    registry,
    app_state,
    *,
    supported_providers: tuple[str, ...],
    manual_factory,
) -> None:
    async def release_allocation(_context, arguments):
        return await app_state.cluster_control.release_allocation(
            str(arguments["allocation_id"])
        )

    async def drain_node(_context, arguments):
        await sync_cluster_nodes(app_state)
        return await app_state.cluster_control.drain_node(str(arguments["node_id"]))

    async def undrain_node(_context, arguments):
        await sync_cluster_nodes(app_state)
        return await app_state.cluster_control.undrain_node(str(arguments["node_id"]))

    registry.register(
        CapabilityDefinition(
            "allocation.release",
            "allocations",
            "runtime_action",
            False,
            supported_providers,
            manual_control=manual_factory(
                label="释放 allocation",
                description="释放指定 allocation，让资源重新进入可调度池",
                risk_level="control",
                approval_policy="confirm_required",
            ),
        ),
        handler=release_allocation,
    )
    registry.register(
        CapabilityDefinition(
            "node.drain",
            "nodes",
            "runtime_action",
            False,
            supported_providers,
            manual_control=manual_factory(
                label="排空节点",
                description="将节点标记为 drained，阻止新作业继续放置到该节点",
                risk_level="control",
                approval_policy="confirm_required",
            ),
        ),
        handler=drain_node,
    )
    registry.register(
        CapabilityDefinition(
            "node.undrain",
            "nodes",
            "runtime_action",
            False,
            supported_providers,
            manual_control=manual_factory(
                label="恢复节点调度",
                description="清除节点 drained 状态，恢复节点可调度性",
                risk_level="operate",
            ),
        ),
        handler=undrain_node,
    )
