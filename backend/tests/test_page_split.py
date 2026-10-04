from app.services.page_split import present_full, present_summary, present_ticket


def _payload():
    return {
        "id": 9,
        "lines": [
            # 缺口 7，临期压到补 4：小票、汇总都必须认 4，不许回退成缺口 7
            {"lane_id": 1, "gap": 7, "fill_cap": 4, "fill_qty": 4, "status": "need_fill",
             "reason": "临期可售不足"},
            # 临期压到补 0 但仍有缺口：是待补不是满仓
            {"lane_id": 2, "gap": 9, "fill_cap": 0, "fill_qty": 0, "status": "need_fill",
             "reason": "临期可售不足"},
            {"lane_id": 3, "gap": 0, "fill_cap": 0, "fill_qty": 0, "status": "full", "reason": ""},
            {"lane_id": 4, "gap": -2, "fill_cap": 0, "fill_qty": 0, "status": "overbooked", "reason": ""},
        ],
        "overbooked_count": 1,
    }


def test_summary_total_equals_ticket_fill_sum():
    s = present_summary(1, _payload())
    assert s["total_fill"] == 4
    assert s["need_fill_count"] == 2
    assert s["full_count"] == 1
    assert s["overbooked_count"] == 1
    assert s["max_fill_qty"] == 4


def test_full_list_keeps_only_true_full_rows():
    body = present_full(1, _payload())
    ids = {l["lane_id"] for l in body["lanes"]}
    # 临期压零的 need_fill(2)、超占(4) 都不许混进满仓页
    assert ids == {3}


def test_ticket_keeps_row_fill_qty():
    payload = {"lines": [{"lane_id": 1, "fill_qty": 4, "gap": 9, "fill_cap": 4}]}
    t = present_ticket(payload)
    assert t["total_fill"] == 4
