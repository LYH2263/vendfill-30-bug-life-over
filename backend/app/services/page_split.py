"""小票 / 汇总 / 满仓三个视图共用同一份补货行，只做投影，不另算口径。

所有数字（fill_qty、fill_cap、gap、status、reason）都来自
fill_engine.summarize 的落库快照，保证销量页、货道卡、小票三处一致。
"""
from __future__ import annotations


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
    total = sum(int(l.get("fill_qty") or 0) for l in lines)

    def count(status: str) -> int:
        return sum(1 for l in lines if str(l.get("status") or "") == status)

    return {
        "location_id": location_id,
        "order_id": payload.get("id"),
        "status": payload.get("status"),
        # 建议总量与小票各行补量合计完全一致，不得回退成缺口合计
        "total_fill": total,
        "need_fill_count": count("need_fill"),
        "full_count": count("full"),
        "overbooked_count": count("overbooked"),
        "blocked_count": payload.get("blocked_count", count("blocked")),
        "capped_count": payload.get("capped_count", count("capped")),
        "sku_cap_full_count": payload.get("sku_cap_full_count", count("sku_cap_full")),
        "max_fill_qty": max((int(l.get("fill_qty") or 0) for l in lines), default=0),
        "fill_open": payload.get("fill_open"),
        "fill_start_minute": payload.get("fill_start_minute"),
        "fill_end_minute": payload.get("fill_end_minute"),
    }


def present_full(location_id: int, payload: dict) -> dict:
    lines = _lines(payload)
    lanes = []
    for l in lines:
        # 满仓页只收缺口为 0 的真满仓行；临期封顶压到补 0 的行仍是
        # need_fill（原因：临期可售不足），不属于满仓，不得混入。
        if int(l.get("gap") or 0) == 0 and str(l.get("status") or "") == "full":
            lanes.append(l)
    return {"location_id": location_id, "lanes": lanes}


def present_sales_cap(row: dict) -> dict:
    # 销量页可补上限直接透传 fill_engine 的 fill_cap，禁止拿 gap 覆盖。
    return dict(row)
