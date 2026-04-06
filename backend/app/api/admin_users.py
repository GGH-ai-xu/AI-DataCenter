from fastapi import APIRouter, HTTPException, Request

from app.api.auth_access import require_admin_user
from app.models.schemas import CreateUserRequest, ResetPasswordRequest


router = APIRouter(prefix="/api/admin", tags=["Admin Users"])


@router.get("/users")
async def list_users(request: Request):
    from app.main import app_state

    require_admin_user(request)
    return {"users": await app_state.identity.list_users()}


@router.post("/users")
async def create_user(request: Request, req: CreateUserRequest):
    from app.main import app_state

    require_admin_user(request)
    try:
        user = await app_state.platform_auth.create_user(
            username=req.username,
            password=req.password,
            role=req.role,
            must_change_password=req.must_change_password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "user": user}


@router.post("/users/{user_id}/reset-password")
async def reset_password(request: Request, user_id: int, req: ResetPasswordRequest):
    from app.main import app_state

    require_admin_user(request)
    try:
        await app_state.platform_auth.reset_password(
            user_id=user_id,
            password=req.password,
            must_change_password=req.must_change_password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"success": True}
