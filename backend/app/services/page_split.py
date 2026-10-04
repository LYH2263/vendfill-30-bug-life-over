"""小票 / 汇总 / 满仓各页的呈现层。

口径铁律：这里只做“搬运和分类”，绝不重新计算补量/上限，更不许用缺口
覆盖小票上的补量。三页同一个数由 fill_engine.lane_stats / build_fill_lines
在算数时就保证，呈现层保持原值。
"""
from __future__ import annotations

from app.services.fill_engine import REASON_EXPIRY


def _lines(payload: dict) -> list[dict]:
    raw = payload.get("lines") or []
    return list(raw)


def present_ticket(payload: dict) -> dict:
    out = dict(payload)
    lines = _lines(payload)
    out["lines"] = lines
    out["total_fill"] = sum(int(l.get("fill_qty") or 0) for l in lines)
    return out


def present_summary(location_id: int, payload: dict) -> dict:
    lines = _lines(payload)
    total_fill = sum(int(l.get("fill_qty") or 0) for l in lines)
    # 计数一律按小票行自身的 status，不再拿“补量为 0”冒充满仓——
    # 被临期上限压到 0 的行仍是待补，不能进满仓数。
    return {
        "location_id": location_id,
        "order_id": payload.get("id"),
        "status": payload.get("status"),
        "total_fill": total_fill,
        "need_fill_count": sum(1 for l in lines if str(l.get("status")) == "need_fill"),
        "full_count": sum(1 for l in lines if str(l.get("status")) == "full"),
        "overbooked_count": sum(1 for l in lines if str(l.get("status")) == "overbooked"),
        "blocked_count": payload.get("blocked_count", 0),
        "capped_count": sum(1 for l in lines if str(l.get("reason")) == REASON_EXPIRY),
        "sku_cap_full_count": payload.get("sku_cap_full_count", 0),
        "max_fill_qty": max((int(l.get("fill_qty") or 0) for l in lines), default=0),
        "fill_open": payload.get("fill_open"),
        "fill_start_minute": payload.get("fill_start_minute"),
        "fill_end_minute": payload.get("fill_end_minute"),
    }


def present_full(location_id: int, payload: dict) -> dict:
    """满仓页：只收真正无需补货的道（缺口 0 的满仓 / 缺口为负的超占 / 封锁）。

    临期封顶把补量压到 0 的行 status 仍是 need_fill——那是“可补为 0”，
    不是满仓，禁止出现在满仓页。
    """
    lanes = []
    for l in _lines(payload):
        status = str(l.get("status") or "")
        if status == "need_fill":
            continue
        fill = int(l.get("fill_qty") or 0)
        if fill == 0 or status in ("full", "blocked", "capped", "sku_cap_full", "overbooked"):
            lanes.append(l)
    return {"location_id": location_id, "lanes": lanes}
