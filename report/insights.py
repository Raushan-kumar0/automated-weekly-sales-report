"""Turns the week's KPIs into a short plain-English summary with three suggested actions.

The wording comes from simple rules: the biggest product, the country with the
biggest drop, the product with the biggest decline, and the size of returns.
"""


def _fmt_change(pct):
    if pct is None:
        return "with no prior week to compare"
    return f"{'up' if pct >= 0 else 'down'} {abs(pct):.1f}% on last week"


def rule_based_summary(kpis: dict) -> dict:
    h = kpis["headline"]
    top = kpis["top_products"][0]
    summary = (f"Revenue was £{h['revenue']['value']:,.0f}, {_fmt_change(h['revenue']['wow_pct'])}, "
               f"from {h['orders']['value']:,} orders ({_fmt_change(h['orders']['wow_pct'])}). "
               f"Average order value was £{h['avg_order_value']['value']:,.0f} and returns came to "
               f"£{h['returns']['value']:,.0f} ({h['returns']['pct_of_revenue']:.1f}% of revenue). "
               f"The top product was {top['product'].title()} at £{top['revenue']:,.0f}. "
               f"{kpis['best_day']['day']} was the busiest day.")
    actions = [f"Check stock of {top['product'].title()}, this week's best seller, for next week."]
    falling = [c for c in kpis["countries"] if c["wow_pct"] is not None and c["wow_pct"] < 0
               and not c["country"].startswith("Other")]
    if falling:
        worst = min(falling, key=lambda c: c["wow_pct"])
        actions.append(f"Look into sales to {worst['country']}, {_fmt_change(worst['wow_pct'])}.")
    drop = kpis.get("biggest_product_drop")
    if drop:
        actions.append(f"Review {drop['product'].title()}: £{drop['last_week']:,.0f} last week, "
                       f"£{drop['revenue']:,.0f} this week.")
    if h["returns"]["pct_of_revenue"] >= 3:
        actions.append(f"Find out what drove £{h['returns']['value']:,.0f} of returns this week.")
    while len(actions) < 3:
        actions.append(f"Plan promotions around {kpis['best_day']['day']}, the strongest sales day.")
    return {"summary": summary, "actions": actions[:3], "source": "rule-based summary"}


def generate_insights(kpis: dict) -> dict:
    return rule_based_summary(kpis)
