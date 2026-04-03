from fastapi import HTTPException, Request


def require_authenticated_user(request: Request) -> dict:
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="请先登录平台")
    return user


def require_admin_user(request: Request) -> dict:
    user = require_authenticated_user(request)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="此操作需要管理员权限")
    return user
