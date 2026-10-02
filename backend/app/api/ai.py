from fastapi import APIRouter, Depends

from app.common.response import Response
from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.ai import ChatMessage, ChatRequest
from app.services import agent_service
from sqlalchemy.orm import Session

router = APIRouter(prefix="/ai", tags=["ai相关的接口"])


@router.post("/chat")
def chat(
    data: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    content = agent_service.run_agent(db, current_user, data)
    return Response.success(data=ChatMessage(role="assistant", content=content))
