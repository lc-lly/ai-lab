from fastapi import APIRouter, Depends
from app.models.user import User
from app.schemas.user import UserResponse
from app.dependencies.auth import get_current_user

router = APIRouter(prefix="/user", tags=["用户信息接口"])


@router.get("/info")
def get_user_info(current_user: User = Depends(get_current_user)):
    return {
        "code": 200,
        "message": "请求成功",
        "data": UserResponse.model_validate(current_user),
    }
