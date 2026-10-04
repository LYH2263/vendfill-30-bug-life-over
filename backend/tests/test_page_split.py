from app.services.fill_engine import REASON_EXPIRY
from app.services.page_split import present_full, present_summary, present_ticket


def test_summary_counts_use_real_fill_and_status():
    payload = {
        "id": 9,
        "lines": [
            # 缺口 7 但被临期压到 4：仍是待补，总量按实际补量 4，不按缺口 7
            {"lane_id": 1, "gap": 7, "fill_qty": 4, "fill_cap": 4,
             "status": "need_fill", "reason": REASON_EXPIRY},
            # 临期压到 0：仍是待补，不许算进满仓
            {"lane_id": 2, "gap": 9, "fill_qty": 0, "fill_cap": 0,
             "status": "need_fill", "reason": REASON_EXPIRY},
            {"lane_id": 3, "gap": 0, "fill_qty": 0, "fill_cap": 0,
             "status": "full", "reason": ""},
            {"lane_id": 4, "gap": -2, "fill_qty": 0, "fill_cap": 0,
             "status": "overbooked", "reason": ""},
        ],
        "overbooked_count": 1,
    }
    s = present_summary(1, payload)
    assert s["total_fill"] == 4            # 不是缺口合计 16
    assert s["need_fill_count"] == 2
    assert s["full_count"] == 1
    assert s["overbooked_count"] == 1
    assert s["capped_count"] == 2
    assert s["max_fill_qty"] == 4


def test_full_list_excludes_capped_need_fill_rows():
    payload = {
        "lines": [
            {"lane_id": 1, "fill_qty": 0, "status": "blocked", "reason": "货道封锁"},
            {"lane_id": 2, "fill_qty": 3, "status": "need_fill", "reason": ""},
            {"lane_id": 3, "fill_qty": 0, "status": "overbooked", "reason": "超占"},
            # 被临期压到 0 的待补道：不是满仓，禁止进满仓页
            {"lane_id": 4, "fill_qty": 0, "status": "need_fill", "reason": REASON_EXPIRY},
            {"lane_id": 5, "fill_qty": 0, "status": "full", "reason": ""},
        ]
    }
    body = present_full(1, payload)
    assert {l["lane_id"] for l in body["lanes"]} == {1, 3, 5}


def test_ticket_keeps_row_fill_qty():
    payload = {"lines": [{"lane_id": 1, "fill_qty": 4, "fill_cap": 4, "gap": 9}]}
    t = present_ticket(payload)
    assert t["total_fill"] == 4            # 不许被缺口 9 覆盖
    assert t["lines"][0]["fill_qty"] == 4
