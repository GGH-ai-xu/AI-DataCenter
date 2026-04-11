from fastapi import APIRouter, HTTPException

from app.api.cluster_jobs import sync_cluster_nodes


router = APIRouter(prefix="/api/cluster", tags=["Cluster"])


def _raise_cluster_error(exc: Exception) -> None:
    if isinstance(exc, LookupError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    raise exc


@router.get("/queues")
async def list_cluster_queues():
    from app.main import app_state

    return {"queues": await app_state.cluster_control.list_queues()}


@router.get("/nodes")
async def list_cluster_nodes():
    from app.main import app_state

    return {"nodes": await sync_cluster_nodes(app_state)}


@router.post("/nodes/{node_id}/drain")
async def drain_cluster_node(node_id: str):
    from app.main import app_state

    try:
        return await app_state.cluster_control.drain_node(node_id)
    except Exception as exc:
        _raise_cluster_error(exc)


@router.post("/nodes/{node_id}/undrain")
async def undrain_cluster_node(node_id: str):
    from app.main import app_state

    try:
        return await app_state.cluster_control.undrain_node(node_id)
    except Exception as exc:
        _raise_cluster_error(exc)


@router.get("/allocations")
async def list_cluster_allocations():
    from app.main import app_state

    return {"allocations": await app_state.store.list_cluster_allocations()}


@router.post("/allocations/{allocation_id}/release")
async def release_cluster_allocation(allocation_id: str):
    from app.main import app_state

    try:
        return await app_state.cluster_control.release_allocation(allocation_id)
    except Exception as exc:
        _raise_cluster_error(exc)
