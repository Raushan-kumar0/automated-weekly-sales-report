"""Emails the finished report (optional: run_report.py --email).

Settings come from .env:
    SMTP_HOST, SMTP_PORT (default 587), SMTP_USER, SMTP_PASSWORD,
    SMTP_STARTTLS (default true), REPORT_FROM, REPORT_TO (comma-separated list)

For Gmail: host smtp.gmail.com, port 587, and an "app password" (not your normal password).
"""
import os
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path


def build_message(report_path: Path, kpis: dict, insights: dict, sender: str, recipients: list[str]) -> EmailMessage:
    rev = kpis["headline"]["revenue"]
    change = "n/a" if rev["wow_pct"] is None else f"{rev['wow_pct']:+.1f}%"
    msg = EmailMessage()
    msg["Subject"] = f"Weekly sales report, week ending {kpis['week_end']}: £{rev['value']:,.0f} ({change} vs last week)"
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    actions = "\n".join(f"{i}. {a}" for i, a in enumerate(insights["actions"], start=1))
    msg.set_content(f"{insights['summary']}\n\nRecommended actions:\n{actions}\n\n"
                    f"The full report is attached (open it in a browser).\n")
    msg.add_attachment(report_path.read_bytes(), maintype="text", subtype="html", filename=report_path.name)
    return msg


def send_report(report_path: Path, kpis: dict, insights: dict) -> list[str]:
    host = os.getenv("SMTP_HOST")
    recipients = [a.strip() for a in os.getenv("REPORT_TO", "").split(",") if a.strip()]
    if not host or not recipients:
        raise SystemExit("To email the report, set SMTP_HOST and REPORT_TO in .env")
    user = os.getenv("SMTP_USER")
    sender = os.getenv("REPORT_FROM") or user or "weekly-report@localhost"
    msg = build_message(report_path, kpis, insights, sender, recipients)

    with smtplib.SMTP(host, int(os.getenv("SMTP_PORT", "587")), timeout=30) as smtp:
        if os.getenv("SMTP_STARTTLS", "true").lower() == "true":
            smtp.starttls(context=ssl.create_default_context())
        if user:
            smtp.login(user, os.getenv("SMTP_PASSWORD", ""))
        smtp.send_message(msg)
    return recipients
