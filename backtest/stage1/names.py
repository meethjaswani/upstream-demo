"""Customer name normalisation and lookup.

Node ids: 'cik:<n>' for SEC filers we track, 'g:<id>' for counterparties from data/graph.json
(used only for names), 'name:<slug>' for named customers we cannot resolve.
"""
import json
import re

STOP = {"inc", "incorporated", "corp", "corporation", "co", "company", "companies", "ltd", "limited", "plc",
        "llc", "lp", "the", "holdings", "holding", "group", "sa", "ag", "nv", "se", "de", "del", "stores",
        "and its subsidiaries", "its", "subsidiaries", "affiliates", "affiliated", "entities", "com"}

# frequent customers written in short forms; value is a ticker (resolved to a CIK) or a fixed node id
MANUAL = {
    "walmart": "WMT", "wal mart": "WMT", "sams club": "WMT", "walmart stores": "WMT",
    "target": "TGT", "home depot": "HD", "lowes": "LOW", "costco": "COST", "costco wholesale": "COST",
    "kroger": "KR", "amazon": "AMZN", "amazoncom": "AMZN", "apple": "AAPL", "mckesson": "MCK",
    "amerisourcebergen": "COR", "cencora": "COR", "cardinal health": "CAH", "cardinal": "CAH",
    "cvs": "CVS", "cvs caremark": "CVS", "cvs health": "CVS", "caremark": "CVS", "aetna": "AET",
    "whole foods": "WFM", "whole foods market": "WFM", "time warner cable": "TWC", "directv": "DTV",
    "kraft foods": "KRFT", "rockwell collins": "COL", "caesars": "CZR", "mgm": "MGM", "penn": "PENN",
    "walgreens": "WBA", "walgreen": "WBA", "walgreens boots alliance": "WBA", "best buy": "BBY",
    "dollar general": "DG", "dollar tree": "DLTR", "general motors": "GM", "gm": "GM", "ford": "F",
    "ford motor": "F", "boeing": "BA", "at and t": "T", "att": "T", "verizon": "VZ", "verizon wireless": "VZ",
    "cellco partnership": "VZ", "tmobile": "TMUS", "comcast": "CMCSA", "charter communications": "CHTR",
    "microsoft": "MSFT", "google": "GOOGL", "alphabet": "GOOGL", "facebook": "META", "intel": "INTC",
    "ibm": "IBM", "international business machines": "IBM", "hewlett packard": "HPQ", "hp": "HPQ",
    "hewlett packard enterprise": "HPE", "cisco": "CSCO", "cisco systems": "CSCO", "oracle": "ORCL",
    "procter and gamble": "PG", "p and g": "PG", "unitedhealth": "UNH", "unitedhealthcare": "UNH",
    "optum": "UNH", "cigna": "CI", "humana": "HUM", "anthem": "ELV", "elevance": "ELV",
    "lockheed martin": "LMT", "raytheon": "name:raytheon", "general dynamics": "GD", "northrop grumman": "NOC",
    "dish network": "DISH", "express scripts": "ESRX", "sprint": "name:sprint",
    "rite aid": "name:rite_aid", "dell": "name:dell", "dell technologies": "name:dell",
    "samsung": "name:samsung", "samsung electronics": "name:samsung", "huawei": "name:huawei",
    "foxconn": "name:hon_hai", "hon hai": "name:hon_hai", "hon hai precision": "name:hon_hai",
    "lenovo": "name:lenovo", "arrow electronics": "name:arrow", "avnet": "name:avnet",
    "ingram micro": "name:ingram_micro", "tech data": "name:tech_data", "synnex": "name:synnex",
    "chrysler": "name:stellantis", "fiat chrysler": "name:stellantis", "fca": "name:stellantis",
    "stellantis": "name:stellantis", "airbus": "name:airbus",
    "us government": "gov:us", "u s government": "gov:us", "united states government": "gov:us",
    "u s federal government": "gov:us", "us federal government": "gov:us", "federal government": "gov:us",
    "department of defense": "gov:us", "u s department of defense": "gov:us", "dod": "gov:us",
    "u s navy": "gov:us", "us navy": "gov:us", "u s army": "gov:us", "us army": "gov:us",
    "u s air force": "gov:us", "us air force": "gov:us", "us dod": "gov:us", "u s dod": "gov:us",
    "medicare": "gov:medicare", "medicaid": "gov:medicaid",
    "centers for medicare and medicaid services": "gov:medicare", "cms": "gov:medicare",
    "cms subsidies": "gov:medicare",
    # spellings produced by splitting XBRL member names and by filers
    "t mobile": "TMUS", "tmobile us": "TMUS", "at t": "T", "atandt": "T", "atandt mobility": "T",
    "at t mobility": "T", "at and t mobility": "T", "at and t wireless": "T", "att mobility": "T",
    "mc kesson": "MCK", "mckesson specialty": "MCK", "mc donalds": "MCD", "mcdonalds": "MCD",
    "amerisource bergen": "COR", "amerisorce bergen": "COR", "mclane": "BRK-B", "mc lane": "BRK-B",
    "us do d": "gov:us", "u s do d": "gov:us", "do d": "gov:us", "maryland procurement office": "gov:us",
    "optumrx": "UNH", "optum rx": "UNH", "sprint nextel": "name:sprint", "medco": "ESRX",
    "celgene": "CELG", "allergan": "AGN", "home depot usa": "HD",
}
# customers later bought by a universe company: (acquired ticker or name node, parent ticker, from date).
# A ticker that cannot be resolved falls back to the 'name:' node of the same customer.
PARENT = [("ESRX", "CI", "2018-12-20"), ("AET", "CVS", "2018-11-28"), ("name:sprint", "TMUS", "2020-04-01"),
          ("CELG", "BMY", "2019-11-20"), ("AGN", "ABBV", "2020-05-08"), ("TWC", "CHTR", "2016-05-18"),
          ("DTV", "T", "2015-07-24"), ("WFM", "AMZN", "2017-08-28"), ("KRFT", "KHC", "2015-07-02"),
          ("COL", "UTX", "2018-11-26"), ("TWX", "T", "2018-06-14"), ("RTN", "UTX", "2020-04-03"),
          ("RHT", "IBM", "2019-07-09"), ("XLNX", "AMD", "2022-02-14"), ("LVLT", "CTL", "2017-11-01"),
          ("FDO", "DLTR", "2015-07-06"), ("DISH", "name:echostar", "2023-12-31")]
# single words too common to use as a name on their own
COMMON = {"general", "united", "american", "international", "national", "first", "southern", "public",
          "global", "health", "energy", "capital", "financial", "services", "systems", "technologies",
          "corporate", "net", "sales", "revenue", "customer", "products", "federal", "state", "total",
          "one", "two", "three", "news", "match", "pool", "progressive", "mosaic", "discovery", "regions",
          "visa", "ball", "gap", "fox", "west", "central", "eastern", "western", "pacific",
          "atlantic", "north", "south", "east", "realty", "trust", "bank", "insurance", "foods", "chemical",
          "resources", "industries", "brands", "partners", "solutions", "communications", "media", "data",
          "us", "u", "s", "other", "others", "all", "remaining", "rest", "unallocated", "eliminations",
          "domestic", "foreign", "americas", "europe", "asia", "corporate", "excludes", "tennessee"}


def norm(s):
    s = s.lower().replace("&", " and ")
    s = re.sub(r"[’'`]", "", s)
    s = re.sub(r"(?<=\w)-(?=\w)", "", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    toks = [t for t in s.split() if t not in STOP]
    while toks and toks[-1] == "and":      # 'Walmart Stores Inc And Affiliates'
        toks.pop()
    return " ".join(toks)


def slug(s):
    return re.sub(r"[^a-z0-9]+", "_", norm(s)).strip("_")


class NameIndex:
    """alias (normalised) -> node id; longest match wins."""

    def __init__(self):
        self.alias = {}
        self.label = {}

    def add(self, name, node, force=False):
        a = norm(name)
        if not a or (len(a.split()) == 1 and a in COMMON):
            return
        if force or a not in self.alias:
            self.alias[a] = node
        self.label.setdefault(node, name)

    def build(self, entity_meta, ticker_to_cik, graph_nodes=()):
        for e in entity_meta:
            node = f"cik:{e['cik']}"
            for n in [e.get("name")] + list(e.get("former_names") or []):
                if n:
                    self.add(n, node)
        for gnode in graph_nodes:
            t = (gnode.get("ticker") or "").upper()
            node = f"cik:{ticker_to_cik[t]}" if t in ticker_to_cik else f"g:{gnode['id']}"
            self.add(gnode["name"], node)
        for a, v in MANUAL.items():
            if ":" in v:
                node = v
            elif v in ticker_to_cik:
                node = f"cik:{ticker_to_cik[v]}"
            else:
                node = f"name:{v.lower()}"
            self.alias[a] = node
            self.label.setdefault(node, a)
        self.maxlen = max(len(a.split()) for a in self.alias)
        return self

    def find(self, text):
        """All non-overlapping alias matches in text: list of (char_start, char_end, node, alias).
        A one-word alias must be capitalised in the original text."""
        toks = [(m.start(), m.end(), m.group(0)) for m in re.finditer(r"[A-Za-z0-9][A-Za-z0-9&'’.\-]*", text)]
        normed = [norm(t[2]) for t in toks]
        out, k = [], 0
        while k < len(toks):
            hit = None
            for L in range(min(self.maxlen, len(toks) - k), 0, -1):
                parts = [p for p in normed[k:k + L] if p]
                if not parts:
                    continue
                a = " ".join(parts)
                if a in self.alias:
                    gov = self.alias[a].startswith("gov:")
                    if not gov and not toks[k][2][:1].isupper():
                        continue          # company names must start with a capital
                    if not normed[k]:
                        continue          # do not start a match on a stop word
                    if len(a.split()) == 1 and not normed[k + L - 1]:
                        continue          # 'Excludes the' is not 'Excludes Limited'
                    hit = (toks[k][0], toks[k + L - 1][1], self.alias[a], a, L)
                    break
            if hit:
                out.append(hit[:4])
                k += hit[4]
            else:
                k += 1
        return out


def camel_words(member):
    """'wmt:WalMartStoresIncMember' -> 'Wal Mart Stores Inc'."""
    local = member.split(":")[-1]
    local = re.sub(r"[.\s]*(Member)?(Domain)?\s*$", "", local)
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", local).strip()
    s = re.sub(r"\bMa?c (?=[A-Z])", lambda m: m.group(0)[:-1], s)      # 'Mc Kesson' -> 'McKesson'
    return s


def load_entity_meta(path):
    return json.loads(open(path).read())
