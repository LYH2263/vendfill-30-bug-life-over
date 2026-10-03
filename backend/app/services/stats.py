"""销量/货道/补货三页共用的货道统计口径。

近七日销量合计 / 7 = 日均；可补上限与补货单补量一律走
fill_engine.lane_stats / build_fill_lines，避免页面各算各的。
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.models import Lane, Sale
from app.services.fill_engine import lane_stats


def sales_7d_map(db: Session, now: datetime | None = None) -> dict[int, int]:
    """每个货道近七日（含时刻对齐的 7×24h）销量合计；无销量不在 map 中。"""
    since = (now or datetime.utcnow()) - timedelta(days=7)
    rows = db.execute(
        select(Sale.lane_id, func.coalesce(func.sum(Sale.qty), 0))
        .where(Sale.sold_at >= since)
        .group_by(Sale.lane_id)
    ).all()
    return {int(lane_id): int(qty or 0) for lane_id, qty in rows}


def lane_payload(lane: Lane, sales_map: dict[int, int]) -> dict:
    """带缺口/日均/可补上限的货道 dict，可直接喂给 build_fill_lines。"""
    base = {
        "id": lane.id,
        "slot_no": lane.slot_no,
        "sku_name": lane.sku_name,
        "capacity": lane.capacity,
        "stock": lane.stock,
        "in_transit": lane.in_transit,
        "sellable_days": lane.sellable_days,
        "sales_7d": sales_map.get(lane.id, 0),
    }
    return {**base, **lane_stats(base)}


def lanes_with_stats(db: Session, lanes, now: datetime | None = None) -> list[dict]:
    sales_map = sales_7d_map(db, now=now)
    return [lane_payload(l, sales_map) for l in lanes]
