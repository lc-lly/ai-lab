from fastapi import APIRouter, Depends
from app.common.response import Response
from app.database import get_db
from sqlalchemy.orm import Session
from app.models.lab import Lab
from app.schemas.lab import LabCreateRequest, LabUpdateRequest
from app.dependencies.auth import get_current_admin
from app.services import lab_service

router = APIRouter(prefix="/lab", tags=["实验室信息接口"])


@router.get("/list")
def get_lab_list(
    page: int = 1,
    page_size: int = 10,
    keywords: str | None = None,
    current_user: Lab = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    res = lab_service.get_lab_page_list(db, page, page_size, keywords)
    return Response.success(data=res)


@router.post("")
def create_lab(
    data: LabCreateRequest,
    current_user: Lab = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    res = lab_service.create_lab(db, data)
    return Response.success(data=res)


@router.put("/{lab_id}")
def update_lab(
    lab_id: int,
    data: LabUpdateRequest,
    current_user: Lab = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    res = lab_service.update_lab(db, lab_id, data)
    return Response.success(data=res)


@router.delete("/{lab_id}")
def delete_lab(
    lab_id: int,
    current_user: Lab = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    lab_service.delete_lab(db, lab_id)
    return Response.success()
