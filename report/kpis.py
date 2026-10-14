"""Pulls one week of sales (and the week before) from MySQL and works out the KPIs.

A week runs Monday to Sunday. Every number is compared with the previous week
(week-over-week, "WoW").
"""
from datetime import date, timedelta

import pandas as pd
from sqlalchemy import text

SALES = "FROM order_lines WHERE line_type = 'sale' AND invoice_date BETWEEN :start AND :end"

SUMMARY_SQL = f"""
    SELECT COALESCE(SUM(revenue), 0)   AS revenue,
           COUNT(DISTINCT invoice_no)  AS orders,
           COUNT(DISTINCT customer_id) AS customers
    {SALES}
"""
RETURNS_SQL = """
    SELECT COALESCE(-SUM(revenue), 0) AS returns_value, COUNT(DISTINCT invoice_no) AS return_invoices
    FROM order_lines
    WHERE line_type = 'return' AND invoice_date BETWEEN :start AND :end
"""
PRODUCT_SQL = f"SELECT description AS product, SUM(revenue) AS revenue, SUM(quantity) AS units {SALES} GROUP BY description"
COUNTRY_SQL = f"SELECT country, SUM(revenue) AS revenue, COUNT(DISTINCT invoice_no) AS orders {SALES} GROUP BY country"
DAILY_SQL = f"""
    SELECT invoice_date, SUM(revenue) AS revenue, COUNT(DISTINCT invoice_no) AS orders
    {SALES}
    GROUP BY invoice_date ORDER BY invoice_date
"""
MIN_REVENUE_FOR_DROP = 1000   # ignore tiny products when looking for the biggest decline


def pct_change(current, previous):
    if previous in (0, None):
        return None
    return round(100.0 * (current - previous) / previous, 1)


def _pct(v):
    """pandas turns None into NaN inside a column; turn it back so 'no comparison' stays None."""
    return None if pd.isna(v) else float(v)


def week_bounds(week_ending: date):
    if week_ending.weekday() != 6:
        raise ValueError(f"{week_ending} is not a Sunday; weeks run Monday to Sunday.")
    start = week_ending - timedelta(days=6)
    return (start, week_ending), (start - timedelta(days=7), start - timedelta(days=1))


def latest_complete_week_ending(engine, today: date | None = None) -> date:
    """Most recent Sunday on/before both today and the last day with data."""
    with engine.connect() as conn:
        last = conn.execute(text("SELECT MAX(invoice_date) FROM order_lines")).scalar()
    cutoff = min(today or date.today(), pd.Timestamp(last).date())
    return cutoff - timedelta(days=(cutoff.weekday() + 1) % 7)


def _q(conn, sql, start, end):
    return pd.read_sql(text(sql), conn, params={"start": start.isoformat(), "end": end.isoformat()})


def _with_last_week(cur: pd.DataFrame, prev: pd.DataFrame, key: str) -> pd.DataFrame:
    out = cur.merge(prev[[key, "revenue"]].rename(columns={"revenue": "last_week"}), on=key, how="left")
    out["revenue"] = out["revenue"].astype(float)
    out["last_week"] = out["last_week"].astype(float).fillna(0)
    out["wow_pct"] = [pct_change(c, p) for c, p in zip(out["revenue"], out["last_week"])]
    return out.sort_values("revenue", ascending=False).reset_index(drop=True)


def build_kpis(engine, week_ending: date) -> dict:
    (start, end), (p_start, p_end) = week_bounds(week_ending)
    with engine.connect() as conn:
        cur, prev = _q(conn, SUMMARY_SQL, start, end).iloc[0], _q(conn, SUMMARY_SQL, p_start, p_end).iloc[0]
        ret, p_ret = _q(conn, RETURNS_SQL, start, end).iloc[0], _q(conn, RETURNS_SQL, p_start, p_end).iloc[0]
        products = _with_last_week(_q(conn, PRODUCT_SQL, start, end), _q(conn, PRODUCT_SQL, p_start, p_end), "product")
        countries = _with_last_week(_q(conn, COUNTRY_SQL, start, end), _q(conn, COUNTRY_SQL, p_start, p_end), "country")
        daily = _q(conn, DAILY_SQL, start, end)

    orders = int(cur["orders"])
    if orders == 0:
        raise SystemExit(f"No sales found between {start} and {end}.")
    revenue, p_revenue = float(cur["revenue"]), float(prev["revenue"])
    p_orders = int(prev["orders"])
    aov, p_aov = revenue / orders, (p_revenue / p_orders if p_orders else 0)
    returns_value, p_returns = float(ret["returns_value"]), float(p_ret["returns_value"])

    daily["invoice_date"] = pd.to_datetime(daily["invoice_date"])
    daily["revenue"] = daily["revenue"].astype(float)
    best = daily.loc[daily["revenue"].idxmax()]

    top_countries = countries.head(5)
    others = countries.iloc[5:]
    country_rows = [{"country": r.country, "revenue": round(r.revenue, 2), "orders": int(r.orders),
                     "share_pct": round(100 * r.revenue / revenue, 1), "wow_pct": _pct(r.wow_pct)}
                    for r in top_countries.itertuples()]
    if len(others):
        o_rev, o_last = others["revenue"].sum(), others["last_week"].sum()
        country_rows.append({"country": f"Other ({len(others)} countries)", "revenue": round(o_rev, 2),
                             "orders": int(others["orders"].sum()), "share_pct": round(100 * o_rev / revenue, 1),
                             "wow_pct": pct_change(o_rev, o_last)})

    drops = products[(products["last_week"] >= MIN_REVENUE_FOR_DROP) & products["wow_pct"].notna()]
    drop = drops.loc[drops["wow_pct"].idxmin()] if len(drops) else None

    return {
        "currency": "£",
        "week_start": start.isoformat(),
        "week_end": end.isoformat(),
        "headline": {
            "revenue": {"value": round(revenue, 2), "last_week": round(p_revenue, 2), "wow_pct": pct_change(revenue, p_revenue)},
            "orders": {"value": orders, "last_week": p_orders, "wow_pct": pct_change(orders, p_orders)},
            "avg_order_value": {"value": round(aov, 2), "last_week": round(p_aov, 2), "wow_pct": pct_change(aov, p_aov)},
            "customers": {"value": int(cur["customers"]), "last_week": int(prev["customers"]),
                          "wow_pct": pct_change(int(cur["customers"]), int(prev["customers"]))},
            "returns": {"value": round(returns_value, 2), "last_week": round(p_returns, 2),
                        "pct_of_revenue": round(100 * returns_value / revenue, 1),
                        "wow_pct": pct_change(returns_value, p_returns)},
        },
        "top_products": [{"product": r.product, "revenue": round(r.revenue, 2), "units": int(r.units), "wow_pct": _pct(r.wow_pct)}
                         for r in products.head(5).itertuples()],
        "biggest_product_drop": None if drop is None or drop["wow_pct"] >= 0 else
            {"product": drop["product"], "revenue": round(float(drop["revenue"]), 2),
             "last_week": round(float(drop["last_week"]), 2), "wow_pct": _pct(drop["wow_pct"])},
        "countries": country_rows,
        "daily": [{"date": d.invoice_date.date().isoformat(), "day": d.invoice_date.strftime("%a"),
                   "revenue": round(d.revenue, 2), "orders": int(d.orders)} for d in daily.itertuples()],
        "best_day": {"day": best["invoice_date"].strftime("%A"), "revenue": round(float(best["revenue"]), 2)},
    }
