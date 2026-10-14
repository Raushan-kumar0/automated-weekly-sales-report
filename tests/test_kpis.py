"""Tests use a tiny in-memory SQLite database, so they run without MySQL."""
from datetime import date

import pandas as pd
import pytest
from sqlalchemy import create_engine

from load_data import clean
from report.insights import rule_based_summary
from report.kpis import build_kpis, latest_complete_week_ending, pct_change, week_bounds

COLS = ["invoice_no", "line_type", "invoice_date", "description", "quantity", "unit_price",
        "revenue", "customer_id", "country"]


@pytest.fixture
def engine():
    eng = create_engine("sqlite://")
    rows = [
        # last week: Mon 21 - Sun 27 Nov 2011
        ("1001", "sale", "2011-11-21", "MUG", 10, 2.0, 20.0, "C1", "United Kingdom"),
        ("1002", "sale", "2011-11-25", "LANTERN", 5, 4.0, 20.0, "C2", "France"),
        # this week: Mon 28 Nov - Sun 4 Dec 2011
        ("1003", "sale", "2011-11-28", "MUG", 20, 2.0, 40.0, "C1", "United Kingdom"),
        ("1003", "sale", "2011-11-28", "LANTERN", 1, 4.0, 4.0, "C1", "United Kingdom"),
        ("1004", "sale", "2011-12-01", "MUG", 5, 2.0, 10.0, None, "Germany"),
        ("C1005", "return", "2011-12-02", "MUG", -2, 2.0, -4.0, "C1", "United Kingdom"),
        # partial next week - must be ignored by "latest complete week"
        ("1006", "sale", "2011-12-05", "MUG", 1, 2.0, 2.0, "C3", "United Kingdom"),
    ]
    pd.DataFrame(rows, columns=COLS).to_sql("order_lines", eng, index=False)
    return eng


def test_pct_change():
    assert pct_change(150, 100) == 50.0
    assert pct_change(10, 0) is None


def test_week_bounds():
    (s, e), (ps, pe) = week_bounds(date(2011, 12, 4))
    assert (s, e, ps, pe) == (date(2011, 11, 28), date(2011, 12, 4), date(2011, 11, 21), date(2011, 11, 27))
    with pytest.raises(ValueError):
        week_bounds(date(2011, 12, 3))


def test_latest_complete_week(engine):
    assert latest_complete_week_ending(engine, today=date(2012, 1, 1)) == date(2011, 12, 4)


def test_kpis(engine):
    k = build_kpis(engine, date(2011, 12, 4))
    h = k["headline"]
    assert h["revenue"]["value"] == 54.0 and h["revenue"]["last_week"] == 40.0
    assert h["orders"]["value"] == 2                 # invoices 1003 and 1004
    assert h["customers"]["value"] == 1              # missing customer IDs aren't counted
    assert h["returns"]["value"] == 4.0
    assert k["top_products"][0]["product"] == "MUG"
    assert k["countries"][0]["country"] == "United Kingdom"


def test_rule_based_summary(engine):
    s = rule_based_summary(build_kpis(engine, date(2011, 12, 4)))
    assert len(s["actions"]) == 3 and "£54" in s["summary"] and s["source"] == "rule-based summary"


def test_cleaning_rules():
    raw = pd.DataFrame({
        "InvoiceNo": ["1", "1", "2", "C3", "4", "5"],
        "StockCode": ["85123A", "85123A", "POST", "85123A", "22423", "22423"],
        "Description": ["MUG", "MUG", "POSTAGE", "MUG", None, "CAKESTAND"],
        "Quantity": [2, 2, 1, -1, 3, 1],
        "InvoiceDate": ["12/1/2010 8:26"] * 6,
        "UnitPrice": [2.5, 2.5, 18.0, 2.5, 0.0, 12.75],
        "CustomerID": ["17850", "17850", "17850", "17850", None, None],
        "Country": ["United Kingdom"] * 6,
    })
    df, log = clean(raw)
    assert log["duplicates_removed"] == 1
    assert log["non_product_lines_removed"] == 1
    assert log["zero_or_negative_price_removed"] == 1
    assert list(df["line_type"]) == ["sale", "return", "sale"]
    assert df["revenue"].tolist() == [5.0, -2.5, 12.75]
