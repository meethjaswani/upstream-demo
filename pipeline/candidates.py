"""Step 3, retrieve candidates: only sentences that could state a link go to the LLM. Keeps API cost low."""
import re
from .parse import sentences

TRIGGER = re.compile(
    r"accounted for|% of (our |the company'?s |total |consolidated |net )*(revenue|sales|net sales|accounts receivable)|"
    r"10% or more|more than 10%|largest customer|major customer|significant customer|principal customer|"
    r"sole[- ]source|single[- ]source|sole supplier|single supplier|limited number of suppliers|"
    r"purchase commitment|purchase obligation|supply agreement|master services agreement|"
    r"customer [A-Z]\b|one customer|two customers|three customers", re.I)
RELATION = re.compile(
    r"\b(supplier|supplies|supply|customer|purchas\w+|manufactur\w+|distribut\w+|licens\w+|agreement|contract|"
    r"invest\w+|stake|equity interest|acquir\w+|partner\w+|relies on|rely on|depend\w+|sells? to|sold to|"
    r"provid\w+ (to|by)|award\w+|order\w*)\b", re.I)


def find(text, entities, filer_id, max_candidates=200):
    """Return [{'pid','section','sentence','passage'}]. Passage adds one sentence either side for context."""
    sents = list(sentences(text))
    out, seen = [], set()
    for i, (section, s) in enumerate(sents):
        hit = TRIGGER.search(s) or (RELATION.search(s) and entities.mentions(s, exclude=filer_id))
        if not hit or s in seen:
            continue
        seen.add(s)
        ctx = " ".join(x[1] for x in sents[max(0, i - 1):i + 2])[:1800]
        out.append({"pid": len(out), "section": section, "sentence": s, "passage": ctx})
        if len(out) >= max_candidates:
            break
    return out
