from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Lane
from app.services.stats import lane_payload, sales_7d_map
router = APIRouter(prefix="/lanes", tags=["lanes"])


class LaneUpdate(BaseModel):
    # None / 缺省 = 留空，不启用临期封顶；≤0 拒绝保存
    sellable_days: int | None = None


def _serialize(r: Lane, sales_map: dict[int, int]) -> dict:
    data = lane_payload(r, sales_map)
    data["fill_pct"] = round(r.stock / r.capacity * 100, 1) if r.capacity else 0
    return data


@router.get("")
def list_lanes(location_id: int | None = None, db: Session = Depends(get_db)):
    q = select(Lane).order_by(Lane.slot_no)
    if location_id is not None: q = q.where(Lane.location_id == location_id)
    return [_serialize(r, sales_7d_map(db)) for r in db.scalars(q).all()]


@router.patch("/{lane_id}")
def update_lane(lane_id: int, body: LaneUpdate, db: Session = Depends(get_db)):
    lane = db.get(Lane, lane_id)
    if not lane:
        raise HTTPException(404, "货道不存在")
    days = body.sellable_days
    if days is not None and days <= 0:
        # 校验先于落库：拒绝保存，库存/可售天数等一切保持改前
        raise HTTPException(400, "临期可售天数必须大于 0；留空表示不启用临期封顶")
    lane.sellable_days = days
    db.commit(); db.refresh(lane)
    return _serialize(lane, sales_7d_map(db))
