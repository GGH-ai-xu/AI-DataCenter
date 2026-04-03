from fastapi import APIRouter, HTTPException, Request

from app.api.auth_access import require_authenticated_user
from app.models.schemas import ChangePasswordRequest, LoginRequest


router = APIRouter(prefix="/api/auth", tags=["Auth"])


@router.post("/login")
async def login(req: LoginRequest):
    from app.main import app_state

    try:
        result = await app_state.platform_auth.login(req.username, req.password)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return {"success": True, **result}


@router.get("/me")
async def me(request: Request):
    return {"user": require_authenticated_user(request)}


@router.post("/logout")
async def logout(request: Request):
    from app.main import app_state

    token = getattr(request.state, "auth_token", "")
    await app_state.platform_auth.logout(token)
    return {"success": True}


@router.post("/change-password")
async def change_password(request: Request, req: ChangePasswordRequest):
    from app.main import app_state

    user = require_authenticated_user(request)
    try:
        await app_state.platform_auth.change_password(
            user_id=user["id"],
            current_password=req.current_password,
            new_password=req.new_password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True}
