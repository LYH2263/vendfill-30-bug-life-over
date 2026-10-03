from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Lane, Sale
from app.services.stats import lanes_with_stats
router = APIRouter(prefix="/sales", tags=["sales"])

@router.get("")
def list_sales(db: Session = Depends(get_db)):
    lane_rows = db.scalars(select(Lane).order_by(Lane.slot_no)).all()
    stats = lanes_with_stats(db, lane_rows)
    by_id = {s["id"]: s for s in stats}
    rows = db.scalars(select(Sale).order_by(Sale.sold_at.desc())).all()
    sales = [{"id": r.id, "lane_id": r.lane_id,
              "slot_no": by_id[r.lane_id]["slot_no"] if r.lane_id in by_id else "",
              "sku_name": by_id[r.lane_id]["sku_name"] if r.lane_id in by_id else "",
              "qty": r.qty, "sold_at": r.sold_at.isoformat()} for r in rows]
    # 每道的近七日销量、日均与由此算出的可补上限，口径与补货单完全一致
    lane_stats = [{
        "lane_id": s["id"], "slot_no": s["slot_no"], "sku_name": s["sku_name"],
        "sales_7d": s["sales_7d"], "avg_daily": round(s["avg_daily"], 4),
        "sellable_days": s["sellable_days"], "gap": s["gap"], "fill_cap": s["fill_cap"],
    } for s in stats]
    return {"sales": sales, "lane_stats": lane_stats}
