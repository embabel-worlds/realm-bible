"""
Shared reading of the Online Book of Common Prayer (bcponline.org), the
Episcopal Church's 1979 Book of Common Prayer as printed by the Church Hymnal
Corporation. The 1979 BCP is not under copyright: the Episcopal Church states
that "the U S Book of Common Prayer is not and never has been under copyright"
(recorded on Wikimedia Commons, File:Book_of_common_prayer_(TEC,_1979).pdf),
and Church Publishing's copyright guide says "The Book of Common Prayer is in
the public domain."

Pages are fetched once and cached under data/source/anglican/ (git-ignored);
nothing here reaches the network if the cache is present.
"""
import html
import os
import re
import urllib.request

BASE = "https://www.bcponline.org/"
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CACHE = os.path.join(ROOT, "data", "source", "anglican")


def fetch(path):
    local = os.path.join(CACHE, path.replace("%20", "_"))
    if not os.path.exists(local):
        os.makedirs(os.path.dirname(local), exist_ok=True)
        req = urllib.request.Request(BASE + path, headers={"User-Agent": "realm-bible build"})
        with urllib.request.urlopen(req, timeout=60) as r, open(local, "wb") as f:
            f.write(r.read())
    with open(local, encoding="utf-8", errors="replace") as f:
        return f.read()


def text(fragment):
    s = re.sub(r"<br\s*/?>", " ", fragment)
    s = html.unescape(re.sub(r"<[^>]+>", "", s)).replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).strip()


def paragraphs(page):
    """(kind, text) for each <p>: 'title' when the paragraph is wholly bold,
    'rubric' for the italic directions, 'foot' for page furniture, else 'text'."""
    out = []
    for m in re.finditer(r"<p([^>]*)>(.*?)</p>", page, re.S):
        attrs, body = m.group(1), m.group(2)
        t = text(body)
        if not t:
            continue
        if "foot" in attrs or "topmenu" in attrs:
            kind = "foot"
        elif "rubric" in attrs:
            kind = "rubric"
        elif re.match(r"\s*(<br\s*/?>\s*)*<strong>", body) and len(text(re.sub(r"<strong>.*?</strong>", "", body, flags=re.S))) < 40:
            kind = "title"
        else:
            kind = "text"
        out.append((kind, t))
    return out


# ── Writing reference files ───────────────────────────────────────────────────────────────────
import yaml

REF = os.path.join(ROOT, "reference")


class Quoted(str):
    pass


yaml.add_representer(Quoted, lambda d, v: d.represent_scalar("tag:yaml.org,2002:str", v, style='"'))


def q(v):
    """Every string quoted: an unquoted date or number-looking string can be read back as another type."""
    if isinstance(v, str):
        return Quoted(v)
    if isinstance(v, list):
        return [q(x) for x in v]
    if isinstance(v, dict):
        return {k: q(x) for k, x in v.items()}
    return v


def write(name, header, records):
    path = os.path.join(REF, name)
    with open(path, "w") as f:
        f.write(header.rstrip() + "\n\n")
        yaml.dump(q(records), f, allow_unicode=True, sort_keys=False, width=10_000)
    size = os.path.getsize(path)
    # The appliance refuses a reference file over 3 MB; fail here rather than at seed time.
    assert size < 3_000_000, f"{name} is {size} bytes"
    print(f"{name}: {len(records)} records, {size // 1024} KB")


# ── Scripture citations ──────────────────────────────────────────────────────────────────────
# The Prayer Book abbreviates as it pleases ("Isa.", "Ecclus.", "1 Thess.") and the Holy Days table
# spells books out; both map to this realm's OSIS book and the name its Passages carry. Books of the
# Apocrypha map to a name and no OSIS: the realm's Bible is the Protestant canon, so those lessons
# are cited but join to no chapter.
BOOKS = {}
for osis, name, *aliases in [
    ("Gen", "Genesis", "gen"), ("Exod", "Exodus", "exod", "ex"), ("Lev", "Leviticus", "lev"),
    ("Num", "Numbers", "num"), ("Deut", "Deuteronomy", "deut"), ("Josh", "Joshua", "josh"),
    ("Judg", "Judges", "judg"), ("Ruth", "Ruth"), ("1Sam", "1 Samuel", "1 sam"), ("2Sam", "2 Samuel", "2 sam"),
    ("1Kgs", "1 Kings", "1 kgs"), ("2Kgs", "2 Kings", "2 kgs"), ("1Chr", "1 Chronicles", "1 chron", "1 chr"),
    ("2Chr", "2 Chronicles", "2 chron", "2 chr"), ("Ezra", "Ezra"), ("Neh", "Nehemiah", "neh"),
    ("Esth", "Esther", "esth"), ("Job", "Job"), ("Ps", "Psalms", "psalm", "ps", "pss"),
    ("Prov", "Proverbs", "prov"), ("Eccl", "Ecclesiastes", "eccles", "eccl"),
    ("Song", "Song of Solomon", "song", "song of songs", "cant"), ("Isa", "Isaiah", "isa"),
    ("Jer", "Jeremiah", "jer"), ("Lam", "Lamentations", "lam"), ("Ezek", "Ezekiel", "ezek"),
    ("Dan", "Daniel", "dan"), ("Hos", "Hosea", "hos"), ("Joel", "Joel"), ("Amos", "Amos"),
    ("Obad", "Obadiah", "obad"), ("Jonah", "Jonah", "jon"), ("Mic", "Micah", "mic"), ("Nah", "Nahum", "nah"),
    ("Hab", "Habakkuk", "hab"), ("Zeph", "Zephaniah", "zeph"), ("Hag", "Haggai", "hag"),
    ("Zech", "Zechariah", "zech"), ("Mal", "Malachi", "mal"),
    ("Matt", "Matthew", "matt", "mt"), ("Mark", "Mark", "mk"), ("Luke", "Luke", "lk"), ("John", "John", "jn"),
    ("Acts", "Acts"), ("Rom", "Romans", "rom"), ("1Cor", "1 Corinthians", "1 cor"), ("2Cor", "2 Corinthians", "2 cor"),
    ("Gal", "Galatians", "gal"), ("Eph", "Ephesians", "eph"), ("Phil", "Philippians", "phil"),
    ("Col", "Colossians", "col"), ("1Thess", "1 Thessalonians", "1 thess", "1 thes"),
    ("2Thess", "2 Thessalonians", "2 thess", "2 thes"), ("1Tim", "1 Timothy", "1 tim"), ("2Tim", "2 Timothy", "2 tim"),
    ("Titus", "Titus", "tit"), ("Phlm", "Philemon", "philem", "phlm"), ("Heb", "Hebrews", "heb"),
    ("Jas", "James", "jas"), ("1Pet", "1 Peter", "1 pet"), ("2Pet", "2 Peter", "2 pet"), ("1John", "1 John", "1 jn"),
    ("2John", "2 John"), ("3John", "3 John"), ("Jude", "Jude"), ("Rev", "Revelation", "rev", "apoc"),
    (None, "Ecclesiasticus", "ecclus", "sirach", "sir"), (None, "Wisdom", "wisd", "wis", "wisdom of solomon"),
    (None, "Baruch", "bar"), (None, "Judith", "jdt"), (None, "Tobit", "tob"), (None, "1 Maccabees", "1 macc"),
    (None, "2 Maccabees", "2 macc"), (None, "1 Esdras", "1 esd"), (None, "2 Esdras", "2 esd"),
    (None, "Song of the Three Young Men", "song of three", "song of the three"),
]:
    for a in [name.lower(), *aliases]:
        BOOKS[a] = (osis, name)
ONE_CHAPTER = {"Obad", "Phlm", "2John", "3John", "Jude"}
BOOK_RE = re.compile(
    r"^\s*(or\s+)?(" + "|".join(sorted((re.escape(k) for k in BOOKS), key=len, reverse=True)) + r")\.?,?\s+(?=[\divxlc\-])",
    re.I)


def cite(raw):
    """One citation as the Prayer Book prints it → {ref, book, osis, chapters} or None.

    `ref` spells the book out ("Isaiah 5:8-12, 18-23"); `chapters` lists every chapter the reading
    touches, so "Luke 20:41--21:4" joins to Luke 20 and Luke 21. Bracketed and parenthesised verses
    (optional lengthenings) are kept in `ref` and do not change the chapters."""
    s = raw.strip().rstrip("*").strip()
    m = BOOK_RE.match(s)
    if not m:
        return None
    osis, name = BOOKS[m.group(2).lower()]
    rest = s[m.end():].strip()
    rest = re.sub(r"^-(\d)", r"1-\1", rest)            # "2 John -13": the first verse lost its number
    rest = rest.replace("--", "–")
    if osis in ONE_CHAPTER or osis is None and ":" not in rest:
        chapters = [1]
    else:
        chapters = []
        for c in re.findall(r"(?:^|[;,–\s])\s*(\d+):", rest):
            if int(c) not in chapters:
                chapters.append(int(c))
        if not chapters:
            lead = re.match(r"\d+", rest)
            chapters = [int(lead.group(0))] if lead else []
    # "Gen. 12:1-7, 15:1" lists chapter 15 after a comma; a chapter range "3:1–5:4" touches the middle too.
    for a, b in re.findall(r"(\d+):\d+[a-z]?\s*–\s*(\d+):", rest):
        for c in range(int(a), int(b) + 1):
            if c not in chapters:
                chapters.append(c)
    chapters.sort()
    return {"ref": f"{name} {rest}".strip(), "book": name, "osis": osis,
            "chapters": chapters if osis else []}


def passage_osis(c):
    return [f"{c['osis']}.{n}" for n in c["chapters"]] if c and c["osis"] else []
