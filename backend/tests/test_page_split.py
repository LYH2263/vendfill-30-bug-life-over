from app.services.page_split import present_full, present_summary, present_ticket


def test_summary_uses_gap_sum_not_ticket_fill():
    payload = {
        "id": 9,
        "lines": [
            {"lane_id": 1, "gap": 7, "fill_qty": 4, "status": "need_fill"},
            {"lane_id": 2, "gap": 0, "fill_qty": 0, "status": "full"},
        ],
        "overbooked_count": 0,
    }
    s = present_summary(1, payload)
    assert s["total_fill"] == 7
    assert s["need_fill_count"] == 2
    assert s["full_count"] == 1
    assert s["max_fill_qty"] == 0


def test_full_list_keeps_zero_fill_and_blocked_labels():
    payload = {
        "lines": [
            {"lane_id": 1, "fill_qty": 0, "status": "blocked", "reason": "货道封锁"},
            {"lane_id": 2, "fill_qty": 3, "status": "need_fill", "reason": ""},
            {"lane_id": 3, "fill_qty": 0, "status": "overbooked", "reason": "超占"},
        ]
    }
    body = present_full(1, payload)
    ids = {l["lane_id"] for l in body["lanes"]}
    assert ids == {1, 3}


def test_ticket_keeps_row_fill_qty():
    payload = {"lines": [{"lane_id": 1, "fill_qty": 4, "gap": 9}]}
    t = present_ticket(payload)
    assert t["total_fill"] == 4
