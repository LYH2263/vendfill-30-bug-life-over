import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Lane, Location, RefillOrder
from app.services.fill_engine import build_fill_lines, summarize
from app.services.page_split import present_full, present_summary, present_ticket
from app.services.stats import lanes_with_stats
router = APIRouter(prefix="/refills", tags=["refills"])


def _current_payload(db: Session, lanes, location_id: int) -> dict:
    """按当前货道状态（含最新临期可售天数、库存、近七日销量）现算一单。"""
    stats = lanes_with_stats(db, lanes)
    return summarize(build_fill_lines(stats))


def _signature(summary: dict) -> tuple:
    """决定补量/上限的全部输入：货道集合 + 容量/库存/在途/可售天数/近七日销量。

    任一项变化（改天数、出货、盘点、加道）都使签名失效，必须重新生成，
    防止小票继续按改前的天数压量。
    """
    keys = ("capacity", "stock", "in_transit", "sellable_days", "sales_7d")
    return tuple(
        (l["lane_id"],) + tuple(l.get(k) for k in keys)
        for l in sorted(summary.get("lines", []), key=lambda l: l["lane_id"])
    )


def _latest_fresh(location_id: int, db: Session) -> tuple[RefillOrder, dict]:
    """取最新一单；若其输入已落后于当前货道状态则当场重算并落新单。"""
    lanes = db.scalars(
        select(Lane).where(Lane.location_id == location_id).order_by(Lane.slot_no)
    ).all()
    current = _current_payload(db, lanes, location_id)
    order = db.scalars(
        select(RefillOrder).where(RefillOrder.location_id == location_id)
        .order_by(RefillOrder.id.desc())
    ).first()
    if order is None:
        order = RefillOrder(location_id=location_id, created_at=datetime.utcnow(),
                            lines_json=json.dumps(current, ensure_ascii=False))
        db.add(order); db.commit(); db.refresh(order)
        return order, current
    stored = json.loads(order.lines_json)
    if _signature(stored) != _signature(current):
        order = RefillOrder(location_id=location_id, created_at=datetime.utcnow(),
                            lines_json=json.dumps(current, ensure_ascii=False))
        db.add(order); db.commit(); db.refresh(order)
    return order, current


@router.post("/run")
def run_refill(location_id: int = 1, db: Session = Depends(get_db)):
    loc = db.get(Location, location_id)
    if not loc: raise HTTPException(404, "点位不存在")
    lanes = db.scalars(select(Lane).where(Lane.location_id == location_id).order_by(Lane.slot_no)).all()
    # 与货道页/销量页同一套「近七日日均 × 可售天数」口径；永远按当前状态现算
    summary = _current_payload(db, lanes, location_id)
    order = RefillOrder(location_id=location_id, created_at=datetime.utcnow(),
                        lines_json=json.dumps(summary, ensure_ascii=False))
    db.add(order); db.commit(); db.refresh(order)
    return present_ticket({"id": order.id, "location_id": location_id, **summary})

@router.get("/latest")
def latest(location_id: int = 1, db: Session = Depends(get_db)):
    loc = db.get(Location, location_id)
    if not loc: raise HTTPException(404, "点位不存在")
    order, current = _latest_fresh(location_id, db)
    return present_ticket({"id": order.id, "location_id": location_id, **current})

@router.get("/full")
def full_lanes(location_id: int = 1, db: Session = Depends(get_db)):
    loc = db.get(Location, location_id)
    if not loc: raise HTTPException(404, "点位不存在")
    order, current = _latest_fresh(location_id, db)
    return present_full(location_id, {"id": order.id, "location_id": location_id, **current})

@router.get("/summary")
def refill_summary(location_id: int = 1, db: Session = Depends(get_db)):
    loc = db.get(Location, location_id)
    if not loc: raise HTTPException(404, "点位不存在")
    order, current = _latest_fresh(location_id, db)
    return present_summary(location_id, {"id": order.id, "location_id": location_id, **current})
