"""Step 5, validate: deterministic checks decide whether a link is stored or sent to the review queue."""
from .parse import norm

TIERS = ["INFERRED", "ANNOUNCED", "STATED", "DISCLOSED"]     # weakest to strongest


def tier_for(link, doc_kind):
    if link.get("inferred"):
        return "INFERRED"
    if doc_kind == "press_release":
        return "ANNOUNCED"
    if link.get("revenue_share") is not None or link.get("amount_usd") is not None:
        return "DISCLOSED"
    return "STATED"


def validate(link, filing_text_norm, filer_id, filer_name, entities, doc_kind, direction_fn=None):
    """Return (record, reasons). Empty reasons means the link passed every check."""
    reasons = []
    quote = norm(link.get("evidence_quote", ""))
    # 1. quote check: must appear word for word in the filing, otherwise treat as hallucinated
    if len(quote) < 20 or quote not in filing_text_norm:
        reasons.append("quote_not_in_source")

    # 2. entity check
    def resolve(name):
        if name.strip().upper() == "FILER":
            return filer_id
        if link.get("anonymised"):
            return f"anon:{filer_id}:{norm(name).lower()}"
        return entities.resolve(name)
    f_id, t_id = resolve(link["from_company"]), resolve(link["to_company"])
    if link["from_company"].strip().upper() == "FILER" and link["to_company"].strip().upper() == "FILER":
        reasons.append("both_sides_filer")
    if f_id is None or t_id is None:
        reasons.append("unknown_entity")
    elif f_id == t_id:
        reasons.append("self_link")
    if filer_id not in (f_id, t_id) and doc_kind != "press_release":
        reasons.append("filer_not_a_party")       # third party links from a filing need a human look

    # 3. number check
    share = link.get("revenue_share")
    if share is not None and not (0 < share <= 1):
        reasons.append("share_out_of_range")
    if link.get("amount_usd") is not None and link["amount_usd"] <= 0:
        reasons.append("amount_not_positive")

    # 4. direction check: a second model call that sees only the quote
    if link["type"] == "sells_to" and not reasons and direction_fn is not None:
        ans = direction_fn(quote, filer_name, link["from_company"], link["to_company"])
        if ans != "A_SELLS_TO_B":
            reasons.append("direction_disagrees:" + ans)

    record = {"from_id": f_id, "to_id": t_id, "type": link["type"], "revenue_share": share,
              "amount_usd": link.get("amount_usd"), "tags": sorted(set(link.get("tags", [])) |
                                                                   ({"anonymised"} if link.get("anonymised") else set())),
              "tier": tier_for(link, doc_kind), "evidence_quote": quote,
              "from_name": link["from_company"], "to_name": link["to_company"]}
    return record, reasons


def share_sum_check(records):
    """Disclosed shares of one seller in one filing must not sum above 1. Returns the offending seller ids."""
    by_quote_seller = {}
    for r in records:
        if r["type"] == "sells_to" and r["revenue_share"] is not None:
            key = (r["from_id"], r["to_id"])
            by_quote_seller[key] = max(by_quote_seller.get(key, 0), r["revenue_share"])   # same pair repeated: keep one
    total = {}
    for (seller, _), s in by_quote_seller.items():
        total[seller] = total.get(seller, 0) + s
    return {s for s, v in total.items() if v > 1.0001}
