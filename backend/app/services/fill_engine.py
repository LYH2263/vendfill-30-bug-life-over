"""Vending refill: gap = capacity - stock - in_transit.

Fill quantity is capped by gap and, when a lane registers 临期可售天数
(sellable_days), also by floor(avg_daily_sales * sellable_days).  The daily
average is the sum of the last 7 days' sales divided by 7; no sales means 0.
Sales page, lanes page and refill orders all consume the SAME stats produced
here so the displayed cap always equals the quantity on the order:

    fill_qty == fill_cap == min(gap, expiry_cap)   （启用临期封顶且有缺口时）

两套上限当场取更紧者：
  - 缺口更紧（cap >= gap）：按缺口补，说明留空，绝不写“临期可售不足”；
  - 天数更紧（cap <  gap）：按临期上限补，说明只写“临期可售不足”，
    绝不写“已满仓/满仓”——没补满不代表满仓。
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass

# Status vocabulary kept stable for the existing UI:
#   need_fill   - 缺口 > 0，正常补货
#   full        - 缺口 = 0，满仓
#   overbooked  - 缺口 < 0，超占
# 当临期封顶使补量小于缺口时，status 仍为 need_fill，原因见 reason。
REASON_EXPIRY = "临期可售不足"


@dataclass
class FillLine:
    lane_id: int
    slot_no: str
    sku_name: str
    capacity: int
    stock: int
    in_transit: int
    gap: int
    fill_qty: int
    status: str  # need_fill | full | overbooked
    sellable_days: int | None = None
    sales_7d: int = 0
    avg_daily: float = 0.0
    fill_cap: int | None = None  # 实际可补上限；None 仅理论上出现（无缺口行也给 0）
    reason: str = ""


def compute_gap(capacity: int, stock: int, in_transit: int) -> int:
    return capacity - stock - in_transit


def daily_avg(sales_7d: int) -> float:
    """近七日销量合计 / 7；销量为 0 则日均为 0。"""
    return (int(sales_7d) or 0) / 7.0


def expiry_cap(avg: float, sellable_days: int | None) -> int | None:
    """floor(日均 × 可售天数)；可售天数留空(None)表示不启用临期封顶。"""
    if sellable_days is None:
        return None
    return math.floor(avg * int(sellable_days))


def lane_stats(lane: dict) -> dict:
    """三页共用的同一套「日均 × 天数」口径。

    返回的 fill_cap 就是“当场可补上限”：启用临期封顶时取缺口与临期上限
    的较小值并夹到非负；未启用时就是非负缺口。小票补量必须等于这个值。
    """
    sales_7d = int(lane.get("sales_7d") or 0)
    days = lane.get("sellable_days")
    # 防御：仅正整数才启用封顶；留空/任何非正值都视为不封顶（非法值在
    # API 层已被拒绝，落不进库，这里只是不让坏数据把补量压成 0）。
    days = int(days) if days is not None and int(days) > 0 else None
    avg = daily_avg(sales_7d)
    cap = expiry_cap(avg, days)
    gap = compute_gap(int(lane["capacity"]), int(lane["stock"]), int(lane["in_transit"]))
    if cap is None:
        effective_cap = max(0, gap)
    else:
        effective_cap = max(0, min(gap, cap))
    return {
        "gap": gap,
        "sales_7d": sales_7d,
        "avg_daily": avg,
        "sellable_days": days,
        "expiry_cap": cap,
        "fill_cap": effective_cap,
    }


def build_fill_lines(lanes: list[dict], requested: dict[int, int] | None = None) -> list[FillLine]:
    """requested optional desired fill per lane_id.

    补量 = max(0, min(期望, 缺口, 临期上限))；临期上限不存在时退化为只按缺口。
    fill_qty 恒等于 lane_stats 给出的 fill_cap（期望更小的情况除外），
    保证销量页上限、货道卡上限、小票该行三者同一个数。
    """
    lines: list[FillLine] = []
    for lane in lanes:
        stats = lane_stats(lane)
        gap = stats["gap"]
        cap = stats["expiry_cap"]      # None=未启用临期封顶
        effective_cap = stats["fill_cap"]
        reason = ""
        if gap < 0:
            status = "overbooked"
            fill = 0
        elif gap == 0:
            status = "full"
            fill = 0
        else:
            status = "need_fill"
            desire = gap if requested is None else int(requested.get(lane["id"], gap))
            desire = max(0, desire)
            if cap is None:
                # 留空不封顶：按缺口（或期望）补，不写任何临期说明。
                fill = min(desire, gap)
            else:
                # 两套上限当场取更紧者；临期上限更紧才写临期说明。
                fill = min(desire, gap, cap)
                if cap < gap:
                    reason = REASON_EXPIRY
        lines.append(FillLine(
            lane_id=lane["id"], slot_no=lane["slot_no"], sku_name=lane["sku_name"],
            capacity=lane["capacity"], stock=lane["stock"], in_transit=lane["in_transit"],
            gap=gap, fill_qty=fill, status=status,
            sellable_days=stats["sellable_days"], sales_7d=stats["sales_7d"],
            avg_daily=stats["avg_daily"], fill_cap=effective_cap, reason=reason,
        ))
    return lines


def summarize(lines: list[FillLine]) -> dict:
    return {
        "total_fill": sum(l.fill_qty for l in lines),
        "need_fill_count": sum(1 for l in lines if l.status == "need_fill"),
        "full_count": sum(1 for l in lines if l.status == "full"),
        "overbooked_count": sum(1 for l in lines if l.status == "overbooked"),
        "capped_count": sum(1 for l in lines if l.reason == REASON_EXPIRY),
        "lines": [asdict(l) for l in lines],
    }
