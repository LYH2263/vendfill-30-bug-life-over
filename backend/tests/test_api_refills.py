"""API 全链路：销量页 / 货道卡 / 小票三页同数，改天数即时重算，非法天数拒绝。

用 SQLite 内存库 + StaticPool，不依赖 Postgres。
"""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture()
def ctx(monkeypatch):
    # 必须在任何 app.* 重模块导入前把数据库指向内存 SQLite
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    monkeypatch.setenv("SEED_ON_EMPTY", "false")

    import app.config as config
    monkeypatch.setattr(config.settings, "database_url", "sqlite://")
    monkeypatch.setattr(config.settings, "seed_on_empty", False)

    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestSession = sessionmaker(bind=test_engine)

    import app.database as database
    monkeypatch.setattr(database, "engine", test_engine)
    monkeypatch.setattr(database, "SessionLocal", TestSession)

    # 此时才首次导入 app.main；它在模块级 from app.database import engine/SessionLocal，
    # 需把 main 自己的绑定也换掉，lifespan 建表才会落在测试内存库上。
    from fastapi.testclient import TestClient
    from app.main import app
    import app.main as main
    monkeypatch.setattr(main, "engine", test_engine)
    monkeypatch.setattr(main, "SessionLocal", TestSession)
    with TestClient(app) as client:
        db = TestSession()
        from app.models.models import Lane, Location, Sale
        loc = Location(code="T1", name="测试点位")
        db.add(loc); db.flush()
        now = datetime.utcnow()

        def add_lane(slot, cap, stock, transit, days, sales_7d):
            lane = Lane(location_id=loc.id, slot_no=slot, sku_name=slot + "商品",
                        capacity=cap, stock=stock, in_transit=transit, sellable_days=days)
            db.add(lane); db.flush()
            if sales_7d:
                db.add(Sale(lane_id=lane.id, qty=sales_7d, sold_at=now - timedelta(hours=1)))
            return lane.id

        ids = {
            "A": add_lane("A", 20, 5, 0, None, 0),   # 空天数零销量：按缺口补 15
            "B": add_lane("B", 20, 5, 0, 2, 14),     # 日均2×2=4 < 缺口15：补4
            "C": add_lane("C", 20, 5, 0, 2, 0),      # 零销量带天数：补0，待补
            "D": add_lane("D", 10, 10, 0, None, 0),  # 满仓
            "E": add_lane("E", 10, 12, 0, None, 0),  # 超占
            "F": add_lane("F", 20, 5, 0, 5, 35),     # 日均5×5=25 > 缺口15：缺口更紧补15
        }
        db.commit(); db.close()
        yield {"client": client, "ids": ids}


def _by_slot(rows, key="slot_no"):
    return {r[key]: r for r in rows}


def test_three_pages_share_one_number(ctx):
    client, ids = ctx["client"], ctx["ids"]
    sales = client.get("/api/sales").json()["lane_stats"]
    lanes = client.get("/api/lanes").json()
    ticket = client.post("/api/refills/run?location_id=1").json()

    s = _by_slot(sales); l = _by_slot(lanes); t = _by_slot(ticket["lines"])
    for slot in ("A", "B", "C", "D", "E", "F"):
        # 销量页上限 == 货道卡上限 == 小票该行上限 == 小票该行补量
        assert s[slot]["fill_cap"] == l[slot]["fill_cap"] == t[slot]["fill_cap"]
        assert t[slot]["fill_qty"] == t[slot]["fill_cap"]

    assert (s["B"]["fill_cap"], s["C"]["fill_cap"], s["A"]["fill_cap"],
            s["F"]["fill_cap"]) == (4, 0, 15, 15)


def test_tight_gap_fills_gap_without_expiry_reason(ctx):
    ticket = _by_slot(ctx["client"].post("/api/refills/run?location_id=1").json()["lines"])
    assert ticket["F"]["fill_qty"] == 15 and ticket["F"]["gap"] == 15
    assert ticket["F"]["reason"] == ""                 # 缺口更紧：不许写临期可售不足


def test_tight_days_caps_with_expiry_reason_never_full(ctx):
    ticket = _by_slot(ctx["client"].post("/api/refills/run?location_id=1").json()["lines"])
    assert ticket["B"]["fill_qty"] == 4 and ticket["B"]["gap"] == 15
    assert ticket["B"]["reason"] == "临期可售不足"      # 天数更紧：只写临期可售不足
    assert "满" not in ticket["B"]["reason"]
    assert ticket["B"]["status"] == "need_fill"
    # 零销量带天数：补 0 但仍待补，说明仍是临期可售不足，不是满仓
    assert ticket["C"]["fill_qty"] == 0
    assert ticket["C"]["status"] == "need_fill"
    assert ticket["C"]["reason"] == "临期可售不足"


def test_full_and_summary_classification(ctx):
    client = ctx["client"]
    client.post("/api/refills/run?location_id=1")
    full = _by_slot(client.get("/api/refills/full?location_id=1").json()["lanes"])
    assert set(full) == {"D", "E"}                    # C 被压到 0 也不许进满仓页

    summary = client.get("/api/refills/summary?location_id=1").json()
    assert summary["full_count"] == 1
    assert summary["overbooked_count"] == 1
    assert summary["need_fill_count"] == 4            # A B C F
    assert summary["total_fill"] == 15 + 4 + 0 + 15   # 实际补量合计，非缺口合计


def test_latest_is_stable_then_recomputes_after_days_change(ctx):
    client, ids = ctx["client"], ctx["ids"]
    first = client.post("/api/refills/run?location_id=1").json()
    again = client.get("/api/refills/latest?location_id=1").json()
    assert again["id"] == first["id"]                  # 输入没变：不重算
    assert _by_slot(again["lines"])["B"]["fill_qty"] == 4

    # 改天数 2 → 3：日均 2 × 3 = 6
    r = client.patch(f"/api/lanes/{ids['B']}", json={"sellable_days": 3})
    assert r.status_code == 200 and r.json()["sellable_days"] == 3

    refreshed = client.get("/api/refills/latest?location_id=1").json()
    assert refreshed["id"] != first["id"]              # 必须新单，不许吃改前的 2 天
    b = _by_slot(refreshed["lines"])["B"]
    assert b["fill_qty"] == 6 and b["fill_cap"] == 6
    assert b["reason"] == "临期可售不足"
    # 销量页当场也是 6
    assert _by_slot(client.get("/api/sales").json()["lane_stats"])["B"]["fill_cap"] == 6


def test_blank_days_lifts_cap_and_drops_reason(ctx):
    client, ids = ctx["client"], ctx["ids"]
    r = client.patch(f"/api/lanes/{ids['B']}", json={"sellable_days": None})
    assert r.status_code == 200 and r.json()["sellable_days"] is None
    ticket = _by_slot(client.get("/api/refills/latest?location_id=1").json()["lines"])
    assert ticket["B"]["fill_qty"] == 15 and ticket["B"]["reason"] == ""


@pytest.mark.parametrize("bad", [0, -1, 2.0, "3", True, False])
def test_illegal_days_rejected_and_pages_keep_previous(ctx, bad):
    client, ids = ctx["client"], ctx["ids"]
    before = client.get("/api/lanes").json()
    before_days = _by_slot(before)["B"]["sellable_days"]
    assert before_days == 2

    r = client.patch(f"/api/lanes/{ids['B']}", json={"sellable_days": bad})
    assert r.status_code == 422

    after = _by_slot(client.get("/api/lanes").json())["B"]
    assert after["sellable_days"] == before_days       # 停在改前
    ticket = _by_slot(client.get("/api/refills/latest?location_id=1").json()["lines"])
    assert ticket["B"]["fill_qty"] == 4                # 小票同样停在改前口径
