from app.services.fill_engine import (
    build_fill_lines, compute_gap, daily_avg, expiry_cap, lane_stats, summarize,
)

def lane(**kw):
    base = {"id": 1, "slot_no": "A1", "sku_name": "水",
            "capacity": 20, "stock": 5, "in_transit": 0,
            "sellable_days": None, "sales_7d": 0}
    base.update(kw)
    return base

def test_gap_basic():
    assert compute_gap(20, 5, 0) == 15
    assert compute_gap(20, 10, 5) == 5

def test_no_negative_fill():
    lines = build_fill_lines([lane(capacity=10, stock=12)])
    assert lines[0].fill_qty == 0
    assert lines[0].status == "overbooked"

def test_cap_by_gap():
    lines = build_fill_lines([lane()], requested={1: 100})
    assert lines[0].fill_qty == 15
    assert lines[0].gap == 15

def test_full_zero_fill():
    s = summarize(build_fill_lines([lane(capacity=10, stock=8, in_transit=2)]))
    assert s["full_count"] == 1
    assert s["total_fill"] == 0

def test_daily_avg_is_sum_over_7():
    assert daily_avg(7) == 1.0
    assert daily_avg(0) == 0.0
    assert daily_avg(2) == 2 / 7

def test_expiry_cap_floors_and_disabled_when_blank():
    assert expiry_cap(2 / 7, 2) == 0          # floor(4/7)
    assert expiry_cap(2.0, 2) == 4
    assert expiry_cap(0.0, 2) == 0
    assert expiry_cap(2.0, None) is None      # 留空不启用

def test_expiry_caps_fill_and_marks_reason():
    # 近七日卖 14 件 → 日均 2；可售 2 天 → 上限 4 < 缺口 15
    lines = build_fill_lines([lane(sales_7d=14, sellable_days=2)])
    l = lines[0]
    assert l.fill_qty == 4
    assert l.fill_cap == 4
    assert l.gap == 15
    assert l.status == "need_fill"            # 不是满仓
    assert l.reason == "临期可售不足"

def test_seed_a1_scenario_floors_to_zero():
    # 种子 A1：容量 20、库存 5、近七日仅 2 件、可售天数 2
    lines = build_fill_lines([lane(sales_7d=2, sellable_days=2)])
    l = lines[0]
    assert l.fill_qty == 0                    # floor(2/7*2)=0
    assert l.fill_cap == 0
    assert l.reason == "临期可售不足"

def test_no_days_means_gap_only():
    lines = build_fill_lines([lane(sales_7d=14)])  # sellable_days 留空
    l = lines[0]
    assert l.fill_qty == 15
    assert l.fill_cap == 15
    assert l.reason == ""

def test_expiry_cap_above_gap_does_not_reduce():
    # 日均 5 × 2 天 = 10，缺口只有 5 → 按缺口补，不写临期原因
    lines = build_fill_lines([lane(stock=15, sales_7d=35, sellable_days=2)])
    l = lines[0]
    assert l.gap == 5
    assert l.fill_qty == 5
    assert l.fill_cap == 5
    assert l.reason == ""

def test_stats_and_order_share_same_cap():
    # 销量页展示的 fill_cap 必须等于补货单行上的补量上限
    data = lane(sales_7d=21, sellable_days=2)
    stats = lane_stats(data)
    line = build_fill_lines([data])[0]
    assert stats["fill_cap"] == line.fill_cap == 6
