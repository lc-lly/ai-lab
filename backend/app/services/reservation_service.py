import asyncio
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload
from datetime import datetime

from app.common.exceptions import BusinessException
from app.common.response import PageResponse
from app.database import SessionLocal
from app.models.equipment import Equipment
from app.models.lab import Lab
from app.models.reservation import Reservation
from app.models.user import User
from app.schemas.reservation import ReservationCreateRequest, ReservationResponse


def get_reservation_page_list(
    db: Session,
    current_user: User,
    page: int,
    page_size: int,
    status: int | None = None,
):
    """查询预约的记录"""
    query = db.query(Reservation)
    if current_user.role != "admin":
        query = query.filter(Reservation.user_id == current_user.id)
    if status is not None:
        query = query.filter(Reservation.status == status)
    total = query.count()
    items = (
        # 预加载关联对象，避免回显 user_name / lab_name 时逐条懒加载（N+1）
        query.options(
            joinedload(Reservation.user),
            joinedload(Reservation.lab),
            joinedload(Reservation.equipment),
        )
        .order_by(Reservation.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    result = []
    for item in items:
        res = ReservationResponse.model_validate(item)
        res.user_name = item.user.name if item.user else None
        res.lab_name = item.lab.name if item.lab else None
        res.equipment_name = item.equipment.name if item.equipment else None
        res.type = "设备" if item.equipment_id else "实验室"
        result.append(res)
    return PageResponse(list=result, total=total)


def create_reservation(db: Session, current_user: User, data: ReservationCreateRequest):
    """创建预约记录"""
    now = datetime.now()
    current_date = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%H:%M")
    if data.date < current_date:
        raise BusinessException(message="预约的日期不能小于当前日期")
    if data.end_time < data.start_time:
        raise BusinessException(message="预约结束时间不能小于开始时间")
    if data.date == current_date and data.start_time < current_time:
        raise BusinessException(message="预约开始时间不能小于当前时间")
    lab = db.query(Lab).filter(Lab.id == data.lab_id).first()
    if not lab:
        raise BusinessException(message="实验室不存在")
    if lab.status != 1:
        raise BusinessException(message="实验室已关闭")
    if lab.open_time and data.start_time < lab.open_time:
        raise BusinessException(message="预约时间不能早于实验室的开放时间")
    if lab.close_time and data.end_time > lab.close_time:
        raise BusinessException(message="预约时间不能晚于实验室的关闭时间")

    # equipment_id 不为空，则表示这次预约的是实验室设备
    if data.equipment_id:
        equipment = (
            db.query(Equipment).filter(Equipment.id == data.equipment_id).first()
        )
        if not equipment:
            raise BusinessException(message="实验室设备不存在")
        if equipment.status != 1:
            raise BusinessException(message="实验室设备正在维修")

    # 实验室或者设置是否是可预约的状态
    query = db.query(Reservation).filter(
        Reservation.lab_id == data.lab_id,
        Reservation.date == data.date,
        Reservation.status.in_([0, 1]),  # 0-待审核 1-已通过
        Reservation.start_time < data.end_time,
        Reservation.end_time > data.start_time,
    )
    # filter 是链式返回新 Query，必须重新赋值，否则条件不会生效
    if data.equipment_id:
        # 预约设备：同一设备的预约冲突，或者实验室已被整间预约也冲突
        query = query.filter(
            or_(
                Reservation.equipment_id == data.equipment_id,
                Reservation.equipment_id.is_(None),
            )
        )
    # 预约整个实验室时不额外过滤：该时段内任何预约（整间或任一设备）都算占用
    if query.first():
        raise BusinessException(message="该时段已预约")

    reservation_model = Reservation(
        user_id=current_user.id,
        lab_id=data.lab_id,
        equipment_id=data.equipment_id,
        date=data.date,
        start_time=data.start_time,
        end_time=data.end_time,
        remark=data.remark,
        status=0,
    )
    db.add(reservation_model)
    db.commit()


def cancel_reservation(db: Session, current_user: User, reservation_id: int):
    """学生取消预约"""
    item = db.query(Reservation).filter(Reservation.id == reservation_id).first()
    if not item:
        raise BusinessException(message="预约记录不存在")
    if item.user_id != current_user.id:
        raise BusinessException(message="无权限", code=403)
    if item.status != 0:
        raise BusinessException(message="当前状态无法取消")
    item.status = 3
    db.commit()


def audit_reservation(db: Session, reservation_id: int, status: int):
    """管理员审核预约"""
    if status not in [1, 2]:
        raise BusinessException(message="审核状态错误")
    item = db.query(Reservation).filter(Reservation.id == reservation_id).first()
    if not item:
        raise BusinessException(message="预约记录不存在")
    if item.status != 0:
        raise BusinessException(message="当前状态不支持审核")
    item.status = status
    db.commit()


def expire_pending_reservation():
    """批量取消过期的审核单"""
    db = SessionLocal()
    try:
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        time = now.strftime("%H:%M")
        itmes = db.query(Reservation).filter(Reservation.status == 0).all()
        changed = False
        for item in itmes:
            if item.date < today or (item.date == today and item.end_time <= time):
                item.status = 3
                changed = True
        if changed:
            db.commit()
    finally:
        db.close()


async def run_expire_scan():
    """一分钟扫描一次执行任务"""
    try:
        while True:
            # 同步的数据库操作放到线程池执行，避免阻塞事件循环
            await asyncio.to_thread(expire_pending_reservation)
            await asyncio.sleep(60)
    except asyncio.CancelledError:
        return
