from fastapi import APIRouter, HTTPException, Request

from app.api.auth_access import require_authenticated_user


router = APIRouter(prefix="/api", tags=["Saved Hosts"])


@router.get("/hosts")
async def list_hosts(request: Request, scope: str = "mine"):
    from app.main import app_state

    user = require_authenticated_user(request)
    return {"hosts": await app_state.saved_hosts.list_hosts(user, scope=scope)}


@router.delete("/hosts/{host_id}")
async def delete_host(request: Request, host_id: int):
    from app.main import app_state

    user = require_authenticated_user(request)
    try:
        await app_state.saved_hosts.delete_host(user, host_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"success": True}
