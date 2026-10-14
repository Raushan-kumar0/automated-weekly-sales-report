"""Checks the email is built and sent correctly, using a fake SMTP server (nothing is really sent)."""
from pathlib import Path

import report.emailer as emailer

KPIS = {"week_end": "2011-12-04", "headline": {"revenue": {"value": 309381.73, "wow_pct": 2.3}}}
INSIGHTS = {"summary": "Revenue was up.", "actions": ["Do A", "Do B", "Do C"]}


class FakeSMTP:
    sent = []

    def __init__(self, host, port, timeout):
        self.host, self.port = host, port

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self, context=None):
        pass

    def login(self, user, password):
        self.user = user

    def send_message(self, msg):
        FakeSMTP.sent.append(msg)


def test_send_report(tmp_path: Path, monkeypatch):
    report = tmp_path / "weekly_report_2011-12-04.html"
    report.write_text("<html>report</html>")
    monkeypatch.setattr(emailer.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("REPORT_TO", "a@example.com, b@example.com")
    monkeypatch.setenv("SMTP_USER", "me@example.com")

    assert emailer.send_report(report, KPIS, INSIGHTS) == ["a@example.com", "b@example.com"]
    msg = FakeSMTP.sent[-1]
    assert "£309,382 (+2.3% vs last week)" in msg["Subject"]
    assert "1. Do A" in msg.get_body(("plain",)).get_content()
    attachment = next(msg.iter_attachments())
    assert attachment.get_filename() == "weekly_report_2011-12-04.html"
