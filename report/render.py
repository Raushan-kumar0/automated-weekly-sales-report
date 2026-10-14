"""Builds the formatted HTML report from the KPIs and the summary."""
import base64
import io
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # no screen needed (works on servers / scheduled runs)
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
from jinja2 import Environment, FileSystemLoader, select_autoescape

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"


def _daily_chart(daily: list[dict]) -> str:
    """Bar chart of revenue per day, returned as a base64 PNG for embedding."""
    fig, ax = plt.subplots(figsize=(7, 2.6), dpi=110)
    ax.bar([d["day"] for d in daily], [d["revenue"] for d in daily], color="#1F3864")
    ax.set_ylabel("Revenue (£)")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v / 1000:,.0f}k"))
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def render_report(kpis: dict, insights: dict, out_dir: Path) -> Path:
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=select_autoescape(["html"]))
    env.filters["gbp"] = lambda v: f"£{v:,.0f}"
    env.filters["num"] = lambda v: f"{v:,}"
    html = env.get_template("weekly_report.html").render(
        k=kpis,
        insights=insights,
        chart_png=_daily_chart(kpis["daily"]),
        generated_at=datetime.now().strftime("%d %b %Y, %H:%M"),
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"weekly_report_{kpis['week_end']}.html"
    path.write_text(html, encoding="utf-8")
    return path
