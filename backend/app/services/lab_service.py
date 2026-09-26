from operator import or_
from app.common.exceptions import BusinessException
from app.common.response import PageResponse
from app.models.lab import Lab
from app.schemas.lab import (
    LabCreateRequest,
    LabResponse,
    LabUpdateRequest,
)
from sqlalchemy.orm import Session


def get_lab_page_list(
    db: Session, page: int, page_size: int, keywords: str | None = None
):
    """分页模糊查询实验室列表"""
    query = db.query(Lab)
    if keywords:
        query = query.filter(
            or_(Lab.name.ilike(f"%{keywords}%"), Lab.location.ilike(f"%{keywords}%"))
        )
    total = query.count()
    items = (
        query.order_by(Lab.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return PageResponse(
        list=[LabResponse.model_validate(item) for item in items], total=total
    )


def create_lab(db: Session, data: LabCreateRequest):
    """新增实验室"""
    exist = db.query(Lab).filter(Lab.name == data.name).first()
    if exist:
        raise BusinessException(message="实验室已存在")
    lab_dict = data.model_dump()
    # {"key1": "value1", "key2": "value2"} -> key1=value1, key2=value2
    lab = Lab(**lab_dict)
    db.add(lab)
    db.commit()
    db.refresh(lab)
    return LabResponse.model_validate(lab)


def update_lab(db: Session, lab_id: int, data: LabUpdateRequest):
    """更新实验室"""
    lab = db.query(Lab).filter(Lab.id == lab_id).first()
    if not lab:
        raise BusinessException(message="实验室不存在")
    payload = data.model_dump(exclude_none=True)
    for field, value in payload.items():
        setattr(lab, field, value)
    db.commit()
    db.refresh(lab)
    return LabResponse.model_validate(lab)


def delete_lab(db: Session, lab_id: int):
    """删除实验室"""
    lab = db.query(Lab).filter(Lab.id == lab_id).first()
    if not lab:
        raise BusinessException(message="实验室不存在")
    db.delete(lab)
    db.commit()
