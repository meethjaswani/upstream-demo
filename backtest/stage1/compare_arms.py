"""Side-by-side step 4 counts for the data arms. Writes results/checkpoint_step4_arms.md."""
import json

from .config import RESULTS


def _get(r, path):
    for k in path.split("."):
        if r is None:
            return None
        r = r.get(k) if isinstance(r, dict) else None
    return r


ROWS = [
    ("Universe companies", "universe_companies"),
    ("Seed links (all)", "seed_links_total"),
    ("Seed links, both ends in universe", "seed_links_both_ends_in_universe"),
    ("Seed seller-buyer pairs in universe", "seed_pairs_both_ends_in_universe"),
    ("Stock-days with a valid FF3 fit", "event_funnel.stock_days_in_index_with_fit"),
    ("abs(z) >= 3", "event_funnel.abs_z_ge_3"),
    ("... and filing/earnings within 1 day", "event_funnel.and_filing_within_1d"),
    ("... and abs(S&P 500) <= 2%: events", "events_total"),
    ("Events, fitting", "events_by_period.fit"),
    ("Events, choosing", "events_by_period.choose"),
    ("Events negative", "events_negative"),
    ("Events on an earnings day", "events_earnings"),
    ("Events with >= 1 linked firm (1 hop)", "events_with_linked_h1"),
    ("Events with >= 5 linked firms (1 hop)", "events_with_5plus_linked_h1"),
    ("Event-firm pairs, 1 hop", "event_firm_pairs_h1"),
    ("  fitting", "event_firm_pairs_h1_by_period.fit"),
    ("  choosing", "event_firm_pairs_h1_by_period.choose"),
    ("Event-firm pairs, up to 4 hops", "event_firm_pairs_h4"),
    ("Pairs left, drop own 8-K/earnings in [0,+5]: fitting", "clean_pairs_drop_any_car_0_5.fit"),
    ("  choosing", "clean_pairs_drop_any_car_0_5.choose"),
    ("Pairs left, drop own 8-K/earnings in [+1,+20]: fitting", "clean_pairs_drop_any_car_1_20.fit"),
    ("  choosing", "clean_pairs_drop_any_car_1_20.choose"),
    ("Pairs left, drop own earnings only, [0,+5]: fitting", "clean_pairs_drop_earn_car_0_5.fit"),
    ("  choosing", "clean_pairs_drop_earn_car_0_5.choose"),
    ("Pairs left, drop own earnings only, [+1,+20]: fitting", "clean_pairs_drop_earn_car_1_20.fit"),
    ("  choosing", "clean_pairs_drop_earn_car_1_20.choose"),
    ("Member-days without a return (2016-2023)", None),
]


def main():
    arms = {a: json.loads((RESULTS / f"checkpoint_step4_{a}.json").read_text()) for a in ("crsp", "yahoo")}
    lines = ["| | CRSP | Yahoo |", "|---|---:|---:|"]
    for label, key in ROWS:
        if key is None:
            c = arms["crsp"]["survivorship"]["share_member_days_without_returns"]
            y = arms["yahoo"]["survivorship"]["share_member_days_without_prices"]
            lines.append(f"| {label} | {c:.1%} | {y:.1%} |")
            continue
        v = [_get(arms[a], key) for a in ("crsp", "yahoo")]
        fmt = lambda x: "" if x is None else (f"{x:,}" if isinstance(x, int) else str(x))
        lines.append(f"| {label} | {fmt(v[0])} | {fmt(v[1])} |")
    text = "\n".join(lines)
    (RESULTS / "checkpoint_step4_arms.md").write_text(
        "# Step 4 counts by data arm (same seed graph, before any model scoring)\n\n" + text + "\n")
    print(text)


if __name__ == "__main__":
    main()
