"""Step 4, extract: the only place the LLM reads filings. Strict tool use forces every record into the schema."""
import hashlib, json, os
from . import config

SYSTEM = """You extract business relationships between companies from SEC filing passages.
The company that filed the document is called FILER. When the passage says "we", "our" or "the Company", that is FILER.

Record a link only when the passage itself states it. Link types and direction:
- sells_to: from_company sells goods or services to to_company (from = seller, to = buyer). Licences count: the licensor sells to the licensee.
- invests_in: from_company owns equity in to_company (from = investor, to = investee).
- partners_with: a named commercial partnership with no clear buyer and seller.

Rules:
- evidence_quote must be copied word for word from the passage, one sentence or less, containing the fact. Never paraphrase or join pieces.
- revenue_share is the share of the SELLER's revenue that comes from the buyer, as a fraction (24% -> 0.24). Null if not stated. Shares of receivables, costs or segment revenue do not count.
- amount_usd is a contract or stake value in US dollars, if stated. Null otherwise.
- Unnamed counterparties ("Customer A", "one customer", "a distributor"): keep them, use the label as written as the name and set anonymised true.
- Set inferred true only if the relationship is implied by indirect wording and not stated outright.
- tags: sole_source (only or single supplier), risk_factor_mention (appears as a risk), purchase_commitment (a committed future purchase).
- Do NOT record: subsidiaries or consolidated joint ventures of FILER, deals that ended or are described as past, executive
  biographies, securitisation or fund trusts, competitors, auditors, banks acting as underwriters or lenders, index providers,
  negated statements ("no customer accounted for more than 10%"), or vague mentions with no buy, sell or ownership relationship.
- If a passage states nothing recordable, return no link for it. Returning an empty list is normal.

Examples:
Passage: "Sales to our largest customer, CVS Health Corporation, accounted for approximately 24% of our total consolidated revenues."
-> sells_to, from FILER, to "CVS Health Corporation", revenue_share 0.24
Passage: "Customer A and Customer B accounted for 22% and 14% of total revenue, respectively."
-> two sells_to links from FILER, to "Customer A" (0.22) and "Customer B" (0.14), anonymised true
Passage: "No single customer accounted for 10% or more of net sales in any period presented."
-> nothing
Passage: "We rely on Taiwan Semiconductor Manufacturing Company as the sole manufacturer of our most advanced chips."
-> sells_to, from "Taiwan Semiconductor Manufacturing Company", to FILER, tags [sole_source, risk_factor_mention]
"""

LINK_TOOL = {
    "name": "record_links",
    "description": "Record every relationship stated in the passages.",
    "strict": True,
    "input_schema": {
        "type": "object", "additionalProperties": False, "required": ["links"],
        "properties": {"links": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["passage_id", "from_company", "to_company", "type", "revenue_share", "amount_usd", "tags",
                         "anonymised", "inferred", "evidence_quote"],
            "properties": {
                "passage_id": {"type": "integer"},
                "from_company": {"type": "string", "description": "Name as written, or FILER"},
                "to_company": {"type": "string", "description": "Name as written, or FILER"},
                "type": {"type": "string", "enum": ["sells_to", "invests_in", "partners_with"]},
                "revenue_share": {"type": ["number", "null"]},
                "amount_usd": {"type": ["number", "null"]},
                "tags": {"type": "array", "items": {"type": "string",
                                                     "enum": ["sole_source", "risk_factor_mention", "purchase_commitment"]}},
                "anonymised": {"type": "boolean"},
                "inferred": {"type": "boolean"},
                "evidence_quote": {"type": "string"}}}}}},
}

DIRECTION_TOOL = {
    "name": "direction",
    "description": "State who sells to whom according to the quote.",
    "strict": True,
    "input_schema": {"type": "object", "additionalProperties": False, "required": ["answer"],
                     "properties": {"answer": {"type": "string", "enum": ["A_SELLS_TO_B", "B_SELLS_TO_A", "UNCLEAR"]}}},
}

_client = None


def client():
    global _client
    if _client is None:
        import anthropic
        _client = anthropic.Anthropic()        # reads ANTHROPIC_API_KEY from the environment
    return _client


def _cached(kind, payload, fn):
    key = hashlib.sha256(json.dumps([kind, config.EXTRACTOR_VERSION, payload], sort_keys=True).encode()).hexdigest()
    path = os.path.join(config.CACHE, "llm", key[:2], key + ".json")
    if os.path.exists(path):
        return json.load(open(path))
    out = fn()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(out, open(path, "w"))
    return out


def _tool_call(model, system, user, tool):
    r = client().messages.create(model=model, max_tokens=4000, system=system, tools=[tool],
                                 tool_choice={"type": "tool", "name": tool["name"]},
                                 messages=[{"role": "user", "content": user}])
    for block in r.content:
        if block.type == "tool_use":
            return block.input
    return {}


def extract(filer_name, form, passages, batch=8, model=None):
    """passages: [{'pid','passage'}]. Returns raw link dicts, each tagged with its passage_id."""
    model = model or config.EXTRACT_MODEL
    links = []
    for i in range(0, len(passages), batch):
        chunk = passages[i:i + batch]
        user = f"FILER: {filer_name}\nForm: {form}\n\n" + "\n\n".join(
            f"[passage_id {p['pid']}]\n{p['passage']}" for p in chunk)
        res = _cached("extract", [model, user], lambda: _tool_call(model, SYSTEM, user, LINK_TOOL))
        ok = {p["pid"] for p in chunk}
        links += [l for l in res.get("links", []) if l.get("passage_id") in ok]
    return links


def check_direction(quote, filer_name, a, b, model=None):
    """Second, short call that sees only the quote. Returns 'A_SELLS_TO_B', 'B_SELLS_TO_A' or 'UNCLEAR'."""
    model = model or config.CHECK_MODEL
    sub = lambda n: f"{filer_name} (the company writing, 'we')" if n == "FILER" else n
    user = (f'Quote from a filing by {filer_name}: "{quote}"\n\nCompany A: {sub(a)}\nCompany B: {sub(b)}\n'
            "According to the quote alone, which company sells goods or services to the other?")
    res = _cached("direction", [model, user],
                  lambda: _tool_call(model, "Answer only from the quote.", user, DIRECTION_TOOL))
    return res.get("answer", "UNCLEAR")
