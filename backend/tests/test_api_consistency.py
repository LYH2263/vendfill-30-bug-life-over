from fastapi.testclient import TestClient

from app.main import app


def _by_slot(rows, key="slot_no"):
    return {r[key]: r for r in rows}


def test_three_pages_show_one_same_number():
    with TestClient(app) as c:
        sales = _by_slot(c.get("/api/sales").json()["lane_stats"])
        lanes = _by_slot(c.get("/api/lanes").json())
        ticket = _by_slot(c.post("/api/refills/run?location_id=1").json()["lines"])
        for slot, t in ticket.items():
            page, card = sales[slot], lanes[slot]
            assert page["fill_cap"] == card["fill_cap"] == t["fill_cap"], slot
            assert t["fill_qty"] == t["fill_cap"], slot


def test_change_days_takes_effect_on_new_order():
    with TestClient(app) as c:
        a1 = _by_slot(c.get("/api/lanes").json())["A1"]
        old_days = a1["sellable_days"]
        # 种子 A1：日均 2/7，天数 2 → floor(4/7)=0
        assert old_days == 2 and a1["fill_cap"] == 0
        ticket = _by_slot(c.post("/api/refills/run?location_id=1").json()["lines"])
        assert (ticket["A1"]["fill_qty"], ticket["A1"]["sellable_days"]) == (0, 2)
        # 改到 30 天：floor(2/7*30)=8，且 sales_7d 不变
        r = c.patch(f"/api/lanes/{a1['id']}", json={"sellable_days": 30})
        assert r.status_code == 200 and r.json()["fill_cap"] == 8
        sales = _by_slot(c.get("/api/sales").json()["lane_stats"])["A1"]
        assert sales["fill_cap"] == 8 and sales["sellable_days"] == 30
        ticket = _by_slot(c.post("/api/refills/run?location_id=1").json()["lines"])
        row = ticket["A1"]
        assert row["fill_qty"] == row["fill_cap"] == 8
        assert row["sellable_days"] == 30 and row["reason"] == "临期可售不足"
        # 还原
        c.patch(f"/api/lanes/{a1['id']}", json={"sellable_days": old_days})


def test_invalid_days_rejected_and_everything_holds_previous():
    with TestClient(app) as c:
        a1 = _by_slot(c.get("/api/lanes").json())["A1"]
        before_days, before_cap = a1["sellable_days"], a1["fill_cap"]
        for bad in (0, -3, True, False, 2.5, "3", 1.0):
            r = c.patch(f"/api/lanes/{a1['id']}", json={"sellable_days": bad})
            assert r.status_code in (400, 422), bad
        a1 = _by_slot(c.get("/api/lanes").json())["A1"]
        # 库存、天数、可补上限全部停在改前
        assert a1["sellable_days"] == before_days and a1["fill_cap"] == before_cap
        ticket = _by_slot(c.post("/api/refills/run?location_id=1").json()["lines"])
        assert ticket["A1"]["fill_qty"] == before_cap


def test_blank_days_disables_cap():
    with TestClient(app) as c:
        a1 = _by_slot(c.get("/api/lanes").json())["A1"]
        old_days = a1["sellable_days"]
        r = c.patch(f"/api/lanes/{a1['id']}", json={"sellable_days": None})
        assert r.status_code == 200
        body = r.json()
        assert body["sellable_days"] is None and body["fill_cap"] == 15
        ticket = _by_slot(c.post("/api/refills/run?location_id=1").json()["lines"])
        assert ticket["A1"]["fill_qty"] == 15 and ticket["A1"]["reason"] == ""
        c.patch(f"/api/lanes/{a1['id']}", json={"sellable_days": old_days})


def test_full_page_excludes_expiry_capped_zero_rows():
    with TestClient(app) as c:
        c.post("/api/refills/run?location_id=1")
        full = {l["slot_no"] for l in c.get("/api/refills/full?location_id=1").json()["lanes"]}
        # A1 被临期压到 0 但有缺口，不得出现在满仓页；A2 才是真满仓
        assert "A1" not in full and "A2" in full
        summ = c.get("/api/refills/summary?location_id=1").json()
        ticket = c.post("/api/refills/run?location_id=1").json()
        assert summ["total_fill"] == sum(l["fill_qty"] for l in ticket["lines"])
