"""Step 2, parse: filing HTML to plain text, split into sentences tagged with their Item section."""
import re
import lxml.html

_ABBR = ["Inc.", "Corp.", "Co.", "Ltd.", "L.P.", "LLC.", "No.", "U.S.", "U.K.", "S.A.", "N.V.", "Mr.", "Ms.", "Dr.",
         "Jr.", "Sr.", "vs.", "approx.", "e.g.", "i.e.", "et al.", "Dec.", "Nov.", "Oct.", "Sept.", "Sep.", "Aug.",
         "Jan.", "Feb.", "Mar.", "Apr.", "Jun.", "Jul.", "N.A.", "p.l.c.", "plc."]
_ITEM = re.compile(r"^\s*item\s+(\d{1,2}[ab]?)\s*[\.:\-–—]", re.I)
_BLOCK = {"p", "div", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6", "br", "table"}


def norm(s):
    """Whitespace normalisation used on both filing text and quotes, so the quote check is fair."""
    return re.sub(r"\s+", " ", s.replace("\xa0", " ").replace("​", "")).strip()


def html_to_text(html):
    try:
        root = lxml.html.fromstring(html.encode("utf-8", "replace"))
    except Exception:
        return norm(re.sub(r"<[^>]+>", " ", html))
    for bad in root.xpath("//script|//style|//head|//*[local-name()='header']|//*[contains(@style,'display:none')]"):
        bad.drop_tree()
    for td in root.xpath("//td|//th"):          # flatten tables: cells joined with a bar
        td.tail = " | " + (td.tail or "")
    for el in root.iter():
        if isinstance(el.tag, str) and el.tag.lower() in _BLOCK:
            el.tail = "\n" + (el.tail or "")
    text = root.text_content()
    lines = [norm(re.sub(r"(\s*\|\s*)+", " | ", l)).strip("| ") for l in text.split("\n")]
    return "\n".join(l for l in lines if l)


def sentences(text):
    """Yield (section, sentence). Section is the latest 'Item N' heading seen, or ''."""
    section = ""
    for line in text.split("\n"):
        m = _ITEM.match(line)
        if m and len(line) < 200:
            section = "Item " + m.group(1).upper()
        safe = line
        for a in _ABBR:
            safe = safe.replace(a, a.replace(".", "\x00"))
        for s in re.split(r"(?<=[.!?])\s+(?=[A-Z“\"(])", safe):
            s = s.replace("\x00", ".").strip()
            if len(s) >= 25:
                yield section, s
