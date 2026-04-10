from fastapi import APIRouter


router = APIRouter(prefix="/api/cluster", tags=["Cluster"])


@router.get("/queues")
async def list_cluster_queues():
    from app.main import app_state

    return {"queues": await app_state.cluster_control.list_queues()}


@router.get("/allocations")
async def list_cluster_allocations():
    from app.main import app_state

    return {"allocations": await app_state.store.list_cluster_allocations()}
