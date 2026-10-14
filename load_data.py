"""
Cleans the Online Retail dataset and loads it into MySQL (run once).

    python load_data.py                 # reads data/data.csv

Dataset: "E-Commerce Data" on Kaggle (carrie1/ecommerce-data), originally the
UCI Online Retail dataset - real transactions from a UK online gift retailer,
Dec 2010 to Dec 2011.

Cleaning rules (each one is counted and printed):
  1. Exact duplicate lines are removed.
  2. Lines with a zero or negative price are removed (stock adjustments, write-offs).
  3. Non-product lines (postage, bank charges, manual adjustments, Amazon fees...) are removed,
     because they aren't sales of goods.
  4. Invoices starting with "C" are kept but marked as returns.
  5. Other lines with zero/negative quantity are removed.
  6. Missing customer IDs are kept (the sale still happened) - they're just left out of
     customer counts.
"""
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from report.db import get_engine

NON_PRODUCT_CODES = {"POST", "DOT", "M", "m", "C2", "D", "S", "B", "BANK CHARGES",
                     "AMAZONFEE", "CRUK", "PADS"}


def read_raw(path: Path) -> pd.DataFrame:
    for enc in ("utf-8-sig", "latin-1"):     # the Kaggle copy is latin-1, some mirrors are utf-8
        try:
            return pd.read_csv(path, encoding=enc, dtype={"InvoiceNo": str, "StockCode": str, "CustomerID": str})
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"Could not read {path}")


def clean(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    df = raw.copy()
    log = {"raw_lines": len(df)}

    before = len(df)
    df = df.drop_duplicates()
    log["duplicates_removed"] = before - len(df)

    bad_price = df["UnitPrice"] <= 0
    log["zero_or_negative_price_removed"] = int(bad_price.sum())
    df = df[~bad_price]

    code = df["StockCode"].str.strip()
    non_product = code.isin(NON_PRODUCT_CODES) | code.str.lower().str.startswith("gift_")
    log["non_product_lines_removed"] = int(non_product.sum())
    df = df[~non_product]

    df["line_type"] = df["InvoiceNo"].str.startswith("C").map({True: "return", False: "sale"})
    bad_qty = (df["line_type"] == "sale") & (df["Quantity"] <= 0)
    log["sale_lines_with_bad_quantity_removed"] = int(bad_qty.sum())
    df = df[~bad_qty]

    log["return_lines"] = int((df["line_type"] == "return").sum())
    log["lines_without_customer_id"] = int(df["CustomerID"].isna().sum())

    ts = pd.to_datetime(df["InvoiceDate"], format="%m/%d/%Y %H:%M")
    clean = pd.DataFrame({
        "invoice_no": df["InvoiceNo"].str.strip(),
        "line_type": df["line_type"],
        "invoice_ts": ts,
        "invoice_date": ts.dt.date,
        "stock_code": df["StockCode"].str.strip().str.upper(),
        "description": df["Description"].fillna("UNKNOWN").str.strip().str.slice(0, 60),
        "quantity": df["Quantity"].astype(int),
        "unit_price": df["UnitPrice"].round(2),
        "revenue": (df["Quantity"] * df["UnitPrice"]).round(2),
        "customer_id": df["CustomerID"].str.replace(r"\.0$", "", regex=True),
        "country": df["Country"].str.strip(),
    })
    log["clean_lines"] = len(clean)
    return clean, log


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/data.csv")
    clean_df, log = clean(read_raw(path))
    for k, v in log.items():
        print(f"  {k:<38} {v:>9,}")

    engine = get_engine()
    schema = Path("sql/schema.sql").read_text(encoding="utf-8")
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS order_lines"))
        conn.execute(text("\n".join(l for l in schema.splitlines() if not l.strip().startswith("--"))))
        clean_df.to_sql("order_lines", conn, if_exists="append", index=False, chunksize=10000, method="multi")
    print(f"Loaded {len(clean_df):,} lines into order_lines "
          f"({clean_df['invoice_date'].min()} to {clean_df['invoice_date'].max()}).")


if __name__ == "__main__":
    main()
