"""Builds the Anglican edition's texts: the collects in both rites, the canticles, the Prayers and
Thanksgivings, the 1979 Psalter, An Outline of the Faith, the Church Catechism, and the Articles of
Religion with Scripture proofs.

    python scripts/anglican/build_texts.py      # from the realm root; downloads into data/source/anglican/

Sources, and why each is free to carry:

- The Book of Common Prayer (1979) of the Episcopal Church, as published online at
  https://www.bcponline.org/ (which follows the current printing). The Episcopal Church states that
  "the U S Book of Common Prayer is not and never has been under copyright", and Church Publishing's
  copyright guide that "the Book of Common Prayer is in the public domain"; both are recorded at
  https://commons.wikimedia.org/wiki/File:Book_of_common_prayer_(TEC,_1979).pdf . Pages read:
    Collects/seasonst.html, holydayst.html (Rite One)  ·  Collects/seasonsc.html, holydaysc.html (Rite Two)
    DailyOffice/mp1.html (Canticles 1-7)  ·  DailyOffice/mp2.html (Canticles 8-21)
    Misc/Prayers.html, Misc/Thanksgivings.html  ·  Psalter/the_psalter.html
    Misc/catechism.html (An Outline of the Faith)  ·  Misc/histdocs.html (Articles of Religion, 1801)
- The Church Catechism of 1662, in the American form the Episcopal Church printed in its Book of
  Common Prayer of 1928 (public domain in the United States: published 1928, and the Church has never
  claimed copyright in its Prayer Book), from the Society of Archbishop Justus' transcription,
  http://justus.anglican.org/resources/bcp/1928/Catechism.htm , read through the Internet Archive
  because the site refuses scripted requests. The English 1662 book itself is NOT used: in the United
  Kingdom its text is Crown property under letters patent, which is why this edition carries no 1662
  collects or office either.
- Scripture proofs for the Articles: "A Catechism of the Thirty-Nine Articles of Religion ... with
  Scripture Proofs" by J. W., second edition (Griffith & Farran, 1877), public domain by age, from the
  New Scriptorium transcription,
  https://newscriptorium.com/assets/books/anglican/39-articles/catechism39.htm . Only the
  references are taken — which texts the compiler cited under which Article — never his wording.
"""
import html
import os
import re
import urllib.request

from common import CACHE, cite, fetch, paragraphs, passage_osis, text, write

UA = {"User-Agent": "Mozilla/5.0 (realm-bible build; https://github.com/embabel-worlds/realm-bible)"}
CATECHISM_1928 = ("https://web.archive.org/web/2024id_/http://justus.anglican.org/resources/bcp/1928/Catechism.htm",
                  "catechism1928-wb.htm")
ARTICLE_PROOFS = ("https://newscriptorium.com/assets/books/anglican/39-articles/catechism39.htm", "catechism39.htm")
PD_1979 = "The Book of Common Prayer (1979), the Episcopal Church — public domain."


def fetch_url(url, name, encoding):
    local = os.path.join(CACHE, name)
    if not os.path.exists(local):
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r, open(local, "wb") as f:
            f.write(r.read())
    with open(local, "rb") as f:
        return f.read().decode(encoding, errors="replace")


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def lines(fragment):
    """Text keeping the printed line breaks: a psalm verse or canticle is laid out in half-verses."""
    s = re.sub(r"<br\s*/?>", "\n", fragment)
    s = html.unescape(re.sub(r"<[^>]+>", "", s)).replace("\xa0", " ")
    out = []
    for ln in s.split("\n"):
        stripped = re.sub(r"\s+", " ", ln).strip()
        if not stripped:
            continue
        # An indented line is the second half of a verse (or a turned line); keep it indented.
        indented = bool(re.match(r"^[ \t]{3,}", ln.replace("\t", "    "))) and out
        out.append(("  " if indented else "") + stripped)
    return "\n".join(out)


# ── Collects ─────────────────────────────────────────────────────────────────────────────────
MONTHS = {m: i + 1 for i, m in enumerate("January February March April May June July August September October November December".split())}


def collect_titles(page):
    """[(title, [collect texts])] in book order. A collect ends at its Amen; page furniture can fall
    inside one, so paragraphs are joined until the Amen arrives. "Preface of …" lines are not prayers."""
    out, cur, buf = [], None, ""
    for kind, t in paragraphs(fetch(page)):
        if kind == "title":
            cur = (t, [])
            out.append(cur)
            buf = ""
        elif kind == "text" and cur is not None and not t.startswith("Preface of"):
            buf = (buf + " " + t).strip()
            if re.search(r"Amen\.?$", buf):
                cur[1].append(buf)
                buf = ""
    return out


def collects():
    records = []
    for kind, pages in (("season", ("Collects/seasonst.html", "Collects/seasonsc.html")),
                        ("holy day", ("Collects/holydayst.html", "Collects/holydaysc.html"))):
        one, two = collect_titles(pages[0]), collect_titles(pages[1])
        assert len(one) == len(two), (pages, len(one), len(two))
        for (t1, c1), (t2, c2) in zip(one, two):
            name = t2
            month_day = ""
            m = re.search(r"\s+(" + "|".join(MONTHS) + r")\s+(\d+)$", name)
            if m:
                month_day = f"{MONTHS[m.group(1)]:02d}-{int(m.group(2)):02d}"
                name = name[:m.start()].strip()
            name = name.replace("All Saint's Day", "All Saints' Day")
            proper = re.match(r"Proper (\d+)\b", name)
            key = f"proper-{proper.group(1)}" if proper else slug(re.sub(r"^The ", "", name.split(":")[0]))
            if proper:
                name = f"Proper {proper.group(1)}"
                closest = re.search(r"closest to (\w+ \d+)", t2)
                note = f"The Sunday closest to {closest.group(1)}" if closest else ""
            else:
                note = ""
            assert c1 and c2, name
            records.append({"type": "Collect", "data": {
                "key": key, "name": name, "kind": kind, "monthDay": month_day, "note": note,
                "rite1": c1[0], "rite2": c2[0],
                "rite1Alternatives": c1[1:], "rite2Alternatives": c2[1:],
            }})
    keys = [r["data"]["key"] for r in records]
    assert len(keys) == len(set(keys)), sorted(k for k in keys if keys.count(k) > 1)
    write("anglican-collects.yml", f"""
# The Collects for the Church Year, in Rite One (traditional) and Rite Two (contemporary): the Sundays
# and seasons, Propers 1-29 after Pentecost, and the Holy Days. {PD_1979}
# Source: https://www.bcponline.org/Collects/ . Generated by scripts/anglican/build_texts.py.
""", records)
    return {r["data"]["key"] for r in records}


# ── Canticles ────────────────────────────────────────────────────────────────────────────────
# The source each canticle is drawn from, as the Prayer Book prints it under the title (Canticles 1-7
# are Rite One's wording of the same songs as 12, 13, 15, 16, 17, 20 and 21).
def canticles():
    records = []
    for page, rite in (("DailyOffice/mp1.html", "One"), ("DailyOffice/mp2.html", "Two")):
        doc = fetch(page)
        end = doc.find('id="acreed"')
        if end < 0:
            end = doc.find("The Apostles' Creed", doc.find('class="x-large"'))
        parts = re.split(r'(?=<strong class="x-large"[^>]*>\d+</strong>)', doc[:end])[1:]
        for part in parts:
            n = int(re.match(r'<strong class="x-large"[^>]*>(\d+)</strong>', part).group(1))
            head = part[:part.find("</p>")]
            title = text(re.findall(r"<strong>(.*?)</strong>", head)[0])
            latin = text((re.findall(r"<em>(.*?)</em>", head) or [""])[0])
            source = text((re.findall(r'<em class="small">(.*?)</em>', head) or [""])[0])
            source = re.sub(r":\s+", ":", source)
            body = part[part.find("</p>") + 4:]
            paras = []
            for m in re.finditer(r"<p([^>]*)>(.*?)</p>", body, re.S):
                if "class=" in m.group(1):
                    continue
                t = lines(m.group(2))
                if t:
                    paras.append(t)
            c = cite(source) if source else None
            records.append({"type": "Canticle", "data": {
                "key": f"canticle-{n}", "number": n, "name": title, "latin": latin, "rite": rite,
                "source": source, "text": "\n\n".join(paras),
            }, **({"relations": [{"predicate": "FROM", "to": {"type": "Passage", "osis": o}} for o in passage_osis(c)]}
                  if passage_osis(c) else {})})
    assert [r["data"]["number"] for r in records] == list(range(1, 22)), [r["data"]["number"] for r in records]
    write("anglican-canticles.yml", f"""
# The twenty-one canticles of Morning and Evening Prayer: 1-7 in Rite One's wording, 8-21 in Rite Two's.
# A biblical canticle is FROM the chapter it is taken from. {PD_1979}
# Source: https://www.bcponline.org/DailyOffice/mp1.html and mp2.html . Generated by scripts/anglican/build_texts.py.
""", records)


# ── Prayers and Thanksgivings ────────────────────────────────────────────────────────────────
def prayers():
    records = []
    for page, kind in (("Misc/Prayers.html", "prayer"), ("Misc/Thanksgivings.html", "thanksgiving")):
        doc = fetch(page)
        doc = re.sub(r'<p class="(leftfoot|rightfoot|topmenu)".*?</p>', "", doc, flags=re.S)
        doc = re.sub(r'<p class="rubric".*?</p>', "", doc, flags=re.S)
        category = ""
        doc = re.sub(r'<em class="rubric">.*?</em>', "", doc, flags=re.S)
        marks = list(re.finditer(r'<strong><a name="([^"]+)">([^<]*)</a>([^<]*)</strong>|<a name="(\d+)">(\d+)\.\s*(.*?)</a>', doc, re.S))
        for i, m in enumerate(marks):
            if m.group(1):
                category = text(m.group(2) + m.group(3))
                continue
            n, title = int(m.group(5)), text(m.group(6))
            end = marks[i + 1].start() if i + 1 < len(marks) else len(doc)
            body = doc[m.end():end]
            body = re.split(r"<(?:h\d|hr)\b", body)[0]
            # Prose, so the printed line breaks go; a blank line (a new paragraph, a versicle) stays.
            body = re.sub(r"</p>|<p[^>]*>", "<br/><br/>", body)
            paras = [text(x) for x in re.split(r"(?:<br\s*/?>\s*){2,}", body)]
            t = re.sub(r"(\w)- ([a-z])", r"\1\2", "\n".join(x for x in paras if x))
            records.append({"type": "BcpPrayer", "data": {
                "key": f"{kind}-{n}", "kind": kind, "number": n, "name": title, "category": category, "text": t,
            }})
    write("anglican-prayers.yml", f"""
# The Prayers and Thanksgivings of the Prayer Book (pages 814-841): seventy prayers and eleven
# thanksgivings, by number, with the heading each stands under. {PD_1979}
# Source: https://www.bcponline.org/Misc/Prayers.html and Thanksgivings.html . Generated by scripts/anglican/build_texts.py.
""", records)


# ── The Psalter ──────────────────────────────────────────────────────────────────────────────
def psalter():
    doc = fetch("Psalter/the_psalter.html")
    psalms, cur = [], None
    for m in re.finditer(r"<td([^>]*)>(.*?)</td>", doc, re.S):
        attrs, body = m.group(1), m.group(2)
        head = re.search(r'<span class="psnum"[^>]*>\s*(\d+|I)\b', body)
        if head:
            cur = {"number": 1 if head.group(1) == "I" else int(head.group(1)), "latin": text((re.findall(r'<span class="pslatin">(.*?)</span>', body) or [""])[0]),
                   "verses": [], "_n": None}
            psalms.append(cur)
            continue
        if cur is None:
            continue
        if 'class="vsnum"' in attrs:
            cur["_n"] = text(body)
            continue
        if cur["_n"]:
            t = lines(body)
            if t:
                cur["verses"].append(f"{cur['_n']} {t}")
            cur["_n"] = None
    byn = {}
    for p in psalms:          # Psalm 119's sections restart the heading; keep one record per psalm
        if p["number"] in byn:
            byn[p["number"]]["verses"] += p["verses"]
        else:
            byn[p["number"]] = p
    assert sorted(byn) == list(range(1, 151)), sorted(set(range(1, 151)) - set(byn))
    records = []
    for n in range(1, 151):
        p = byn[n]
        records.append({"type": "BcpPsalm", "data": {
            "key": f"psalm-{n}", "number": n, "name": f"Psalm {n}", "latin": p["latin"],
            "verseCount": len(p["verses"]), "verses": p["verses"],
        }, "relations": [{"predicate": "SAME_AS", "to": {"type": "Passage", "osis": f"Ps.{n}"}}]})
    write("anglican-psalter.yml", f"""
# The Psalter of the 1979 Prayer Book: each psalm with its Latin incipit and its verses as printed, the
# asterisk marking the half-verse. Each is the SAME_AS the realm's chapter of Psalms. {PD_1979}
# Source: https://www.bcponline.org/Psalter/the_psalter.html . Generated by scripts/anglican/build_texts.py.
""", records)


# ── An Outline of the Faith ─────────────────────────────────────────────────────────────────
def outline():
    doc = fetch("Misc/catechism.html")
    records, section, part_no, number, q = [], "", 0, 0, None
    for m in re.finditer(r'<p[^>]*class="cattopic"[^>]*>(.*?)</p>|<tr>(.*?)</tr>', doc, re.S):
        if m.group(1):
            section, part_no = text(m.group(1)), part_no + 1
            continue
        cells = re.findall(r"<td[^>]*>(.*?)</td>", m.group(2), re.S)
        if len(cells) != 2:
            continue
        label, body = text(cells[0]), text(cells[1])
        if not body:
            continue
        if label.startswith("Q"):
            number += 1
            q = {"type": "CatechismEntry", "data": {
                "key": f"bcp-1979/{number}", "catechism": "An Outline of the Faith (BCP 1979)", "catechismId": "bcp-1979",
                "part": section, "partNumber": part_no, "section": section, "number": number,
                "question": body, "text": "", "note": ""}}
            records.append(q)
        elif q is not None:
            q["data"]["text"] = (q["data"]["text"] + "\n" + body).strip() if label.startswith("A") or q["data"]["text"] else body
    assert len(records) > 100, len(records)
    write("anglican-catechism-outline.yml", f"""
# An Outline of the Faith, commonly called the Catechism, from the 1979 Prayer Book (pages 845-862):
# every question and answer, in the book's order, under its section. {PD_1979}
# The Outline gives no Scripture proofs, so none are invented here.
# Source: https://www.bcponline.org/Misc/catechism.html . Generated by scripts/anglican/build_texts.py.
""", records)


# ── The Church Catechism (1662, American form) ─────────────────────────────────────────────
def church_catechism():
    doc = fetch_url(*CATECHISM_1928, "latin-1")
    s = re.sub(r"<(?:br|p|/p|td|/td|tr|/tr)\b[^>]*>", " ", doc, flags=re.I)
    s = html.unescape(re.sub(r"<[^>]+>", "", s)).replace("\xa0", " ")
    s = re.sub(r"\s+", " ", s)
    s = s[s.upper().find("QUESTION. WHAT IS YOUR NAME"):]
    s = re.split(r"\s(?:¶|The Book of Common Prayer \(1928\)\s*$)", s)[0]
    # The transcription doubles the Third Commandment's closing clause; the printed book has it once.
    s = s.replace("that taketh his Name in vain; for the LORD will not hold him guiltless, that taketh his name in vain.",
                  "that taketh his Name in vain.")
    turns = re.split(r"\s(QUESTION\.|Question\.|Catechist\.|Answer\.)\s", " " + s)
    records, number, cur = [], 0, None
    for i in range(1, len(turns) - 1, 2):
        who, said = turns[i], turns[i + 1].strip()
        if who != "Answer.":
            number += 1
            cur = {"key": f"church-catechism/{number}", "catechism": "The Church Catechism (1662, American form of 1928)",
                   "catechismId": "church-catechism", "part": "A Catechism", "partNumber": 1, "section": "",
                   "number": number, "question": said, "text": "", "note": ""}
            records.append({"type": "CatechismEntry", "data": cur})
        else:
            cur["text"] = said
    # Where the Catechism itself names its Scripture, it is a proof: the Commandments are "the same which
    # God spake in the twentieth Chapter of Exodus". Nothing else in it cites chapter and verse.
    for r in records:
        sections = [("Your Baptism", 0), ("The Creed", 4), ("The Commandments", 6), ("The Lord's Prayer", 11), ("The Sacraments", 13)]
        d = r["data"]
        d["section"] = [t for t, start in sections if d["number"] > start][-1]
        if "twentieth Chapter of Exodus" in d["text"]:
            r["relations"] = [{"predicate": "PROVED_BY", "to": {"type": "Passage", "osis": "Exod.20"}}]
            d["proofTexts"] = ["Exodus 20:1-17"]
        if d["question"].startswith("My good Child") or "Lord's Prayer" in d["question"] or "Lord’s Prayer" in d["question"]:
            if "Our Father" in d["text"]:
                r["relations"] = [{"predicate": "PROVED_BY", "to": {"type": "Passage", "osis": "Matt.6"}}]
                d["proofTexts"] = ["Matthew 6:9-13"]
                d["note"] = "The proof text is the Lord's Prayer as Matthew records it; the Catechism quotes the prayer without citing it."
    assert len(records) > 20, len(records)
    write("anglican-catechism-1662.yml", """
# The Church Catechism ("A Catechism, that is to say, an Instruction to be learned of every person before
# he be brought to be confirmed by the Bishop"), the catechism of the 1662 Prayer Book in the American form
# printed in the Episcopal Church's Book of Common Prayer of 1928 (public domain in the United States).
# The English 1662 printing is not used: its text is Crown property in the United Kingdom.
# Source: http://justus.anglican.org/resources/bcp/1928/Catechism.htm (via web.archive.org). Generated by scripts/anglican/build_texts.py.
""", records)


# ── The Articles of Religion ───────────────────────────────────────────────────────────────
ROMAN = {v: i + 1 for i, v in enumerate(
    "I II III IV V VI VII VIII IX X XI XII XIII XIV XV XVI XVII XVIII XIX XX XXI XXII XXIII XXIV XXV XXVI XXVII XXVIII XXIX XXX "
    "XXXI XXXII XXXIII XXXIV XXXV XXXVI XXXVII XXXVIII XXXIX".split())}


def roman_to_int(s):
    vals, total, prev = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100}, 0, 0
    for ch in reversed(s.lower()):
        v = vals[ch]
        total += -v if v < prev else v
        prev = max(prev, v)
    return total


def article_proofs():
    """{article number: [citations]} — every Scripture reference the 1877 catechism cites under each Article, in order."""
    doc = fetch_url(*ARTICLE_PROOFS, "cp1252")
    s = html.unescape(re.sub(r"<[^>]+>", " ", doc)).replace("\xa0", " ")
    s = re.sub(r"[ \t\r\n]+", " ", s)
    heads = list(re.finditer(r"\b(?:Article|ARTICLE) ([IVXL]+)\.?(?=\s+[A-Z“\"])", s))
    out = {}
    for i, h in enumerate(heads):
        n = ROMAN.get(h.group(1))
        if not n or n in out:
            continue
        body = s[h.end(): heads[i + 1].start() if i + 1 < len(heads) else len(s)]
        # "Num. xxiii, 19" — the compiler sometimes wrote chapters in Roman numerals.
        body = re.sub(r"\b([ivxlc]+), (\d+)", lambda m: f"{roman_to_int(m.group(1))}:{m.group(2)}", body)
        seen, refs = set(), []
        for m in re.finditer(r"(?:(?<=\s)|^)((?:[123] )?[A-Z][a-z]+\.?(?: of [A-Z][a-z]+)?) (\d+):(\d+(?:[–-]\d+)?(?:, ?\d+(?:[–-]\d+)?)*)", body):
            c = cite(f"{m.group(1)} {m.group(2)}:{m.group(3).replace(', ', ',')}")
            if not c or not c["osis"]:
                continue
            ref = f"{c['book']} {m.group(2)}:{m.group(3)}".replace("–", "-")
            if ref not in seen:
                seen.add(ref)
                refs.append((ref, c))
        out[n] = refs
    return out


def articles():
    doc = fetch("Misc/histdocs.html")
    start = doc.find('name="articles"')
    end = doc.find("Chicago-Lambeth", start)
    # Article VI lists the canonical and the apocryphal books in tables, printed in columns; each table
    # becomes one paragraph, read down each column as the book is.
    def columns(table):
        rows = [[text(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)] for r in re.findall(r"<tr[^>]*>(.*?)</tr>", table, re.S)]
        width = max((len(r) for r in rows), default=0)
        return "<p>" + " ".join(r[k] for k in range(width) for r in rows if k < len(r) and r[k]) + "</p>"
    body = re.sub(r"<table.*?</table>", lambda m: columns(m.group(0)), doc[start:end], flags=re.S)
    ps = [(k, t) for k, t in paragraphs(body)]
    records, cur, expected = [], None, 1
    for kind, t in ps:
        m = re.match(r"^([IVXL]+)\.\s+(Of .*?\.)\s*(.*)$", t)
        if kind != "foot" and m and m.group(1) in ROMAN and (ROMAN[m.group(1)] == expected or m.group(1) in ("XVII", "XVIII") and expected in (27, 28)):
            # The online text misprints XXVII and XXVIII as XVII and XVIII; the sequence decides.
            cur = {"number": expected, "title": m.group(2), "paras": [m.group(3)] if m.group(3) else [], "original": ""}
            records.append(cur)
            expected += 1
        elif cur is not None and kind in ("text", "rubric") and not re.match(r"^\d+\s+Historical|Historical Documents\s+\d+$", t):
            if t.startswith("The original 1571, 1662 text"):
                cur["original"] = t
            elif cur["original"] and not t.startswith("["):
                cur["original"] += "\n" + t
            else:
                cur["paras"].append(t)
    assert [r["number"] for r in records] == list(range(1, 40)), [r["number"] for r in records]
    proofs = article_proofs()
    out = []
    for r in records:
        refs = proofs.get(r["number"], [])
        rel = []
        for _, c in refs:
            for o in passage_osis(c):
                if {"predicate": "PROVED_BY", "to": {"type": "Passage", "osis": o}} not in rel:
                    rel.append({"predicate": "PROVED_BY", "to": {"type": "Passage", "osis": o}})
        roman = [k for k, v in ROMAN.items() if v == r["number"]][0]
        body = "\n\n".join(p for p in r["paras"] if p)
        out.append({"type": "ArticleOfReligion", "data": {
            "key": f"article-{r['number']}", "number": r["number"], "roman": roman, "title": r["title"],
            "text": body, "original1571": r["original"],
            "omitted": r["number"] == 21,
            "proofTexts": [ref for ref, _ in refs],
        }, **({"relations": rel} if rel else {})})
    write("anglican-articles.yml", f"""
# The Articles of Religion (the Thirty-Nine Articles of 1571) as the Episcopal Church established them in
# 1801, printed among the Historical Documents of the 1979 Prayer Book; where the American text departs
# from 1571 (Articles VIII, XXI, XXXVI, XXXVII) the Prayer Book gives the original, carried as
# `original1571`. {PD_1979} Source: https://www.bcponline.org/Misc/histdocs.html#articles .
# Each Article is PROVED_BY the chapters that J. W.'s "A Catechism of the Thirty-Nine Articles ... with
# Scripture Proofs" (2nd ed., 1877; public domain) cites under it — references only, not his text.
# Source: https://newscriptorium.com/assets/books/anglican/39-articles/catechism39.htm .
# Generated by scripts/anglican/build_texts.py.
""", out)


if __name__ == "__main__":
    collects()
    canticles()
    prayers()
    psalter()
    outline()
    church_catechism()
    articles()
