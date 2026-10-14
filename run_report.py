"""
Generates the weekly sales report.

    python run_report.py                          # latest complete week (Mon-Sun)
    python run_report.py --week-ending 2025-06-22 # a specific week (must be a Sunday)

Steps: pull KPIs from MySQL -> write summary -> save HTML report -> (optional) email it.
Schedule it weekly with cron / Windows Task Scheduler (see README).
"""
import argparse
import json
from datetime import date
from pathlib import Path

from report.db import get_engine
from report.emailer import send_report
from report.insights import generate_insights
from report.kpis import build_kpis, latest_complete_week_ending
from report.render import render_report

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description="Generate the weekly sales report.")
    parser.add_argument("--week-ending", type=date.fromisoformat,
                        help="Sunday that ends the week to report on (YYYY-MM-DD)")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "reports")
    parser.add_argument("--save-json", action="store_true", help="also save the raw KPIs as JSON")
    parser.add_argument("--email", action="store_true", help="email the report (SMTP settings in .env)")
    args = parser.parse_args()

    engine = get_engine()
    week_ending = args.week_ending or latest_complete_week_ending(engine)

    kpis = build_kpis(engine, week_ending)
    insights = generate_insights(kpis)
    path = render_report(kpis, insights, args.out_dir)

    if args.save_json:
        (args.out_dir / f"kpis_{kpis['week_end']}.json").write_text(json.dumps(kpis, indent=2), encoding="utf-8")

    h = kpis["headline"]["revenue"]
    wow = "n/a" if h["wow_pct"] is None else f"{h['wow_pct']:+.1f}%"
    print(f"Week {kpis['week_start']} to {kpis['week_end']}: revenue £{h['value']:,.0f} "
          f"({wow} WoW). Summary by: {insights['source']}")
    print(f"Report saved to {path}")

    if args.email:
        sent_to = send_report(path, kpis, insights)
        print(f"Report emailed to {', '.join(sent_to)}")


if __name__ == "__main__":
    main()
