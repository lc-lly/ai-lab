from fastapi import APIRouter, Depends
from app.common.exceptions import BusinessException
from app.common.response import Response
from app.schemas.auth import LoginRequest, LoginResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.schemas.user import UserResponse
from app.utils.password import verify_password
from app.utils.jwt import create_access_token

router = APIRouter(prefix="/auth", tags=["权限验证接口"])


@router.post("/login")
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == data.username).first()

    # 判断账户密码是否正确
    if not user or not verify_password(data.password, user.password):
        raise BusinessException(message="账户或密码错误")
    if user.status != 1:
        raise BusinessException(message="账户已被禁用")
    token = create_access_token(user.id)

    return Response.success(
        message="登录成功",
        data=LoginResponse(token=token, user=UserResponse.model_validate(user)),
    )
