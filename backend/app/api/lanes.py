from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Lane
from app.services.stats import lane_payload, sales_7d_map
router = APIRouter(prefix="/lanes", tags=["lanes"])

# 仅接受严格正整数：拒绝 bool/浮点/字符串/0/负数（strict 拒绝 2.0 与 "2"，
# gt=0 拒绝 0 与负数）；None / 缺省 = 留空，不启用临期封顶。
PositiveInt = Annotated[int, Field(strict=True, gt=0)]


class LaneUpdate(BaseModel):
    sellable_days: PositiveInt | None = None


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
    days = body.sellable_days  # 到这里只可能是正整数或 None（非法值已在入参校验被 422 拒绝）
    lane.sellable_days = days
    db.commit(); db.refresh(lane)
    return _serialize(lane, sales_7d_map(db))
