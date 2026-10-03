"""Builds the Daily Office for 2025-2030: one OfficeDay for each morning and each evening, carrying the
day's place in the church year, the psalms and lessons the 1979 Prayer Book appoints, the collect, and
the canticles the Prayer Book suggests.

    python scripts/anglican/build_office.py      # from the realm root; after build_texts.py

Everything is computed here, at build time, from the Prayer Book's own rules and tables — the realm
never works out a date at query time, and a view never knows what "today" is.

Sources (the Episcopal Church's Book of Common Prayer, 1979 — public domain; see build_texts.py):
  The Daily Office Lectionary, pages 934-1001: https://www.bcponline.org/DOLectionary/dolectionary.html
    (Advent.html, Christmas.html, Epiphany.html, Lent.html, Easter.html, Pentecost.html, Holy%20Days.html)
  The Calendar of the Church Year, pages 15-33: https://www.bcponline.org/General/calendar.html
  The Table of Suggested Canticles, pages 144-145: https://www.bcponline.org/DailyOffice/canticle.html
  "Concerning the Proper of the Church Year", page 158: https://www.bcponline.org/Collects/proper.html

The Prayer Book's rules applied:
- Year One of the lectionary begins on the First Sunday of Advent preceding odd-numbered years.
- Of a day's three readings, two are read in the morning and one in the evening; the Gospel is read in
  the evening in Year One and in the morning in Year Two (page 934). Where the table marks a reading
  for the morning or the evening, the mark decides.
- Sundays after Pentecost take the numbered Proper whose date is closest to the Sunday; the weekdays of
  Pentecost and Trinity weeks take the Proper closest to that Sunday (pages 158, 966).
- Principal Feasts take precedence of any day. The Holy Name, the Presentation and the Transfiguration
  take precedence of a Sunday; any other Holy Day falling on a Sunday is transferred to the first open
  day. Feasts are not observed in Holy Week or Easter Week, and move to the week after (page 16-17).
  The First Sunday after Christmas takes precedence over the three Holy Days that follow Christmas Day,
  which are each postponed one day as necessary (page 161).
- The Eve of a feast gives the psalms and lessons for the evening before it.

The Prayer Book appoints no liturgical colours. The colour carried is the widespread custom, named as
custom wherever it is shown; Advent is given as blue, the colour most Episcopal parishes use, with
violet as the old use.
"""
import datetime as dt
import re

from dateutil.easter import easter

from common import cite, fetch, passage_osis, text, write

YEARS = range(2025, 2031)
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
ORD = ["", "First", "Second", "Third", "Fourth", "Fifth", "Sixth", "Seventh", "Eighth"]
PAGES = ["Advent", "Christmas", "Epiphany", "Lent", "Easter", "Pentecost"]


# ── Reading the lectionary tables ────────────────────────────────────────────────────────────
def cell_text(fragment):
    """A table cell as text, keeping the runs of spaces that separate the three lessons."""
    s = fragment.replace('<span style="font-family: Wingdings">v</span>', " ◊ ")
    s = re.sub(r"<br\s*/?>", " ", s)
    s = re.sub(r"&nbsp;", "\xa0", s)
    s = text(s.replace("\xa0", "\x01"))      # text() collapses whitespace; keep the hard spaces apart
    return s.replace("\x01", "\xa0")


def split_lessons(s):
    return [t.strip(" \xa0") for t in re.split(r"(?:\xa0\s*){2,}|\s{3,}", s) if t.strip(" \xa0")]


def section_of(heading):
    h = re.sub(r"\s+", " ", heading.replace("\xa0", " ")).strip()
    m = re.match(r"Proper (\d+)", h)
    if m:
        return ("Proper", int(m.group(1)))
    m = re.match(r"Week of (\d+|Last) (Advent|Epiphany|Lent|Easter)", h)
    if m:
        return (m.group(2), "last" if m.group(1) == "Last" else int(m.group(1)))
    return (h,)


def parse_page(name):
    """{'one': {(section, label): entry}, 'two': {...}}. Each printed page ends in a running footer naming
    its year, so rows are buffered and handed to the year the next footer names."""
    doc = fetch(f"DOLectionary/{name}.html")
    years = {"one": {}, "two": {}}
    buf, section = [], None
    for m in re.finditer(r"<tr[^>]*>(.*?)</tr>|<p[^>]*>(.*?)</p>", doc, re.S):
        if m.group(2) is not None:
            foot = text(m.group(2))
            year = "one" if "Year One" in foot else "two" if "Year Two" in foot else None
            if year:
                assign(buf, years[year])
                buf = []
            continue
        cells = re.findall(r"<td[^>]*>(.*?)</td>", m.group(1), re.S)
        if len(cells) < 2:
            continue
        buf.append((cell_text(cells[0]), cell_text(cells[1]), "<strong>" in cells[1]))
    assert not [r for r in buf if r[1].strip()], (name, buf[:3])
    return years


def assign(rows, table):
    section, entry, notes = None, None, {}
    entries = []
    for label, right, bold in rows:
        label = label.strip(" \xa0")
        r = right.strip(" \xa0")
        if not r and not label:
            continue
        if not label and bold and "◊" not in r:
            section = section_of(r)
            continue
        if "◊" in r:
            mp, ep = [x.strip(" \xa0") for x in r.split("◊")]
            entry = {"label": norm_label(label), "section": section, "psalms": [clean_psalms(mp), clean_psalms(ep)],
                     "rawEvening": ep, "lessons": []}
            entries.append(entry)
            table[(section, entry["label"])] = entry
            table.setdefault(("*", entry["label"]), entry)
            continue
        if r.startswith("*"):
            stars = re.match(r"\*+", r).group(0)
            notes[stars] = r[len(stars):].strip()
            continue
        if entry is None:
            continue
        for tok in split_lessons(r):
            mark = "m" if re.search(r"[^*]\*\*$", tok) else "e" if tok.endswith("***") else ""
            tok = tok.rstrip("*").strip()
            if re.fullmatch(r"-{3,}", tok):
                entry["lessons"].append(None)
            elif tok.startswith("or ") and entry["lessons"]:
                first = next(i for i, x in enumerate(entry["lessons"]) if x)
                entry["lessons"][first] = (entry["lessons"][first][0] + "; or " + cite(tok[3:])["ref"], entry["lessons"][first][1])
            elif cite(tok):
                entry["lessons"].append((cite(tok)["ref"], mark))
    # "*If today is Saturday, use Psalms 23 and 27 at Evening Prayer." — kept with the entries it marks.
    for e in entries:
        stars = re.search(r"(\*+)$", e["rawEvening"])
        if stars and stars.group(1) in notes:
            e["saturdayEvening"] = notes[stars.group(1)]


def norm_label(label):
    l = label.replace("\xa0", " ").strip().rstrip("*").strip()
    m = re.match(r"(Dec|Jan)\.? ?(\d+)\.?$", l)
    if m:
        return f"{m.group(1)}. {int(m.group(2))}"
    return l


def clean_psalms(s):
    s = s.strip(" \xa0")
    if re.fullmatch(r"-{3,}", s) or not s:
        return ""
    s = re.sub(r"95\*\s*&\s*", "95 (Invitatory) & ", s)
    return re.sub(r"\*+$", "", s).strip()


def psalm_numbers(s):
    out = []
    for item in re.split(r"[,;&]|\bor\b", s):
        m = re.match(r"\s*\[?\s*(\d+)", item)
        if m and int(m.group(1)) not in out and 1 <= int(m.group(1)) <= 150:
            out.append(int(m.group(1)))
    return out


def parse_holy_days():
    doc = fetch("DOLectionary/Holy%20Days.html")
    out = {}
    for m in re.finditer(r"<tr[^>]*>(.*?)</tr>", doc, re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", m.group(1), re.S)
        if len(cells) != 3:
            continue
        name = text(re.sub(r"<em>.*?</em>", "", cells[0], flags=re.S))
        when = text(" ".join(re.findall(r"<em>(.*?)</em>", cells[0], re.S)))
        if not name or name == "Holy Days":
            continue

        def office(c):
            parts = [text(x) for x in re.split(r"<br\s*/?>", c)]
            parts = [p for p in parts if p]
            if not parts:
                return None
            psalms, lessons = parts[0], []
            for p in parts[1:]:
                if p.startswith("or ") and lessons:
                    lessons[-1] = lessons[-1] + "; or " + cite(p[3:])["ref"]
                else:
                    sub = re.split(r"\s+or\s+(?=[1-3]?\s?[A-Z])", p)
                    lessons.append("; or ".join(cite(x)["ref"] for x in sub))
            return {"psalms": re.sub(r",(?=\S)", ", ", psalms), "lessons": lessons}
        out[name] = {"name": name, "when": when, "morning": office(cells[1]), "evening": office(cells[2])}
    return out


# ── The Calendar of the Church Year: the commemorations the Prayer Book lists ─────────────────
def parse_calendar():
    doc = fetch("General/calendar.html")
    months = "January February March April May June July August September October November December".split()
    out, month = {}, None
    for m in re.finditer(r"<tr[^>]*>(.*?)</tr>", doc, re.S):
        cells = [text(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", m.group(1), re.S)]
        if len(cells) < 3:
            continue
        if cells[2] in months and not cells[0]:
            month = months.index(cells[2]) + 1
            continue
        if month and cells[0].isdigit() and cells[2]:
            out[(month, int(cells[0]))] = cells[2]
    assert len(out) > 100, len(out)
    return out


# ── The church year ──────────────────────────────────────────────────────────────────────────
def advent1(y):
    christmas = dt.date(y, 12, 25)
    last_sunday = christmas - dt.timedelta(days=(christmas.weekday() + 1) % 7 or 7)
    return last_sunday - dt.timedelta(weeks=3)


def sunday_on_or_before(d):
    return d - dt.timedelta(days=(d.weekday() + 1) % 7)


def proper_for(sunday):
    return round((sunday - dt.date(sunday.year, 5, 11)).days / 7) + 1


# Holy Days on fixed dates, by the name the Holy Days table uses: (month, day, collect key, colour, our-Lord?)
HOLY_DAYS = [
    ("St. Andrew", 11, 30, "red"), ("St. Thomas", 12, 21, "red"), ("St. Stephen", 12, 26, "red"),
    ("St. John", 12, 27, "white"), ("Holy Innocents", 12, 28, "red"), ("Confession of St. Peter", 1, 18, "white"),
    ("Conversion of St. Paul", 1, 25, "white"), ("The Presentation", 2, 2, "white"), ("St. Matthias", 2, 24, "red"),
    ("St. Joseph", 3, 19, "white"), ("The Annunciation", 3, 25, "white"), ("St. Mark", 4, 25, "red"),
    ("SS. Philip & James", 5, 1, "red"), ("The Visitation", 5, 31, "white"), ("St. Barnabas", 6, 11, "red"),
    ("Nativity of St. John the Baptist", 6, 24, "white"), ("SS. Peter &Paul", 6, 29, "red"),
    ("Independence Day", 7, 4, "white"), ("St. Mary Magdalene", 7, 22, "white"), ("St. James", 7, 25, "red"),
    ("The Transfiguration", 8, 6, "white"), ("St. Mary the Virgin", 8, 15, "white"),
    ("St. Bartholomew", 8, 24, "red"), ("Holy Cross Day", 9, 14, "red"), ("St. Matthew", 9, 21, "red"),
    ("St. Michael & All Angels", 9, 29, "white"), ("St. Luke", 10, 18, "red"),
    ("St. James of Jerusalem", 10, 23, "red"), ("SS. Simon & Jude", 10, 28, "red"),
    ("All Saints' Day", 11, 1, "white"),
]
LORDS_FEASTS_OVER_SUNDAY = {"The Presentation", "The Transfiguration"}     # and the Holy Name, handled in Christmas
EVES = {"The Presentation": "Eve of the Presentation", "The Annunciation": "Eve of the Annunciation",
        "The Visitation": "Eve of the Visitation", "Nativity of St. John the Baptist": "Eve of St. John the Baptist",
        "The Transfiguration": "Eve of the Transfiguration", "Holy Cross Day": "Eve of Holy Cross",
        "All Saints' Day": "Eve of All Saints"}
DISPLAY = {"St.": "Saint", "SS.": "Saint", "&Paul": "and Saint Paul", "& James": "and Saint James",
           "& Jude": "and Saint Jude", "& All Angels": "and All Angels"}


def display_name(n):
    out = n
    for a, b in DISPLAY.items():
        out = out.replace(a, b)
    return re.sub(r"\s+", " ", out)


class Year:
    """Everything about one civil year's days that depends on Easter and Advent."""

    def __init__(self, y, collects_by_day):
        self.y = y
        self.easter = easter(y)
        self.ash = self.easter - dt.timedelta(days=46)
        self.adv = advent1(y)
        self.prev_adv = advent1(y - 1)
        self.epiphany1 = dt.date(y, 1, 6) + dt.timedelta(days=7 - (dt.date(y, 1, 6).weekday() + 1) % 7)
        self.holy = self.place_holy_days()

    def principal(self, d):
        e = self.easter
        return d in (e, e + dt.timedelta(39), e + dt.timedelta(49), e + dt.timedelta(56),
                     dt.date(self.y, 11, 1), dt.date(self.y, 12, 25), dt.date(self.y, 1, 6))

    def closed(self, d):
        """No Holy Day is observed here: a Sunday, a Principal Feast, Ash Wednesday, Holy Week or Easter Week."""
        e = self.easter
        return (d.weekday() == 6 or self.principal(d) or d == self.ash
                or e - dt.timedelta(7) <= d <= e + dt.timedelta(6))

    def place_holy_days(self):
        taken, out = {}, {}
        christmas_sunday = next((dt.date(self.y, 12, d) for d in range(26, 32) if dt.date(self.y, 12, d).weekday() == 6), None)
        for name, mo, day, colour in sorted(HOLY_DAYS, key=lambda h: (h[1], h[2])):
            d = dt.date(self.y, mo, day)
            if name in LORDS_FEASTS_OVER_SUNDAY and not self.principal(d):
                pass
            elif name in ("St. Stephen", "St. John", "Holy Innocents"):
                # Postponed one day as the First Sunday after Christmas requires, keeping their order.
                while d == christmas_sunday or d in taken:
                    d += dt.timedelta(1)
            elif name == "All Saints' Day":
                pass
            else:
                if self.easter - dt.timedelta(7) <= d <= self.easter + dt.timedelta(6):
                    d = self.easter + dt.timedelta(8)       # the Monday after the Second Sunday of Easter
                while self.closed(d) or d in taken:
                    d += dt.timedelta(1)
            taken[d] = name
            out[d] = (name, colour, dt.date(self.y, mo, day))
        # Thanksgiving Day: the fourth Thursday of November.
        nov1 = dt.date(self.y, 11, 1)
        thanks = nov1 + dt.timedelta(days=(3 - nov1.weekday()) % 7 + 21)
        out[thanks] = ("Thanksgiving Day", "white", thanks)
        return out


def office_year(d):
    """'one' or 'two' — Year One begins at Advent before an odd-numbered year."""
    church_year = d.year + 1 if d >= advent1(d.year) else d.year
    return "one" if church_year % 2 else "two"


def place(d, Y):
    """Where d falls: (table section, label, season, sunday name, collect key, colour, rank)."""
    wd = WEEKDAYS[d.weekday()]
    e = Y.easter
    y = d.year
    if d >= Y.adv and d < dt.date(y, 12, 25):
        n = (d - Y.adv).days // 7 + 1
        key = f"{ORD[n].lower()}-sunday-of-advent"
        name = f"The {ORD[n]} Sunday of Advent" if wd == "Sunday" else f"{wd} in the {ORD[n]} Week of Advent"
        return (("Advent", n), wd, "Advent", name, key, "blue", "sunday" if wd == "Sunday" else "weekday")
    if d.month == 12 and d.day >= 25 or d.month == 1 and d.day <= 5:
        cy = y if d.month == 12 else y - 1
        xsun = next((dt.date(cy, 12, k) for k in range(26, 32) if dt.date(cy, 12, k).weekday() == 6), None)
        jsun = next((dt.date(cy + 1, 1, k) for k in range(2, 6) if dt.date(cy + 1, 1, k).weekday() == 6), None)
        if d == dt.date(cy, 12, 25):
            return (("*",), "Christmas Day", "Christmas", "The Nativity of Our Lord: Christmas Day", "nativity-of-our-lord", "white", "principal feast")
        if d == dt.date(cy + 1, 1, 1):
            return (("*",), "Holy Name", "Christmas", "The Holy Name of Our Lord Jesus Christ", "holy-name", "white", "feast of our Lord")
        if d == xsun:
            return (("*",), "First Sunday after Christmas", "Christmas", "The First Sunday after Christmas Day", "first-sunday-after-christmas-day", "white", "sunday")
        if d == jsun:
            return (("*",), "Second Sunday after Christmas", "Christmas", "The Second Sunday after Christmas Day", "second-sunday-after-christmas-day", "white", "sunday")
        label = f"{'Dec' if d.month == 12 else 'Jan'}. {d.day}"
        if d.month == 12:
            key = "first-sunday-after-christmas-day" if xsun and d > xsun else "nativity-of-our-lord"
        else:
            key = "second-sunday-after-christmas-day" if jsun and d > jsun else "holy-name"
        return (("*",), label, "Christmas", f"{wd} after Christmas", key, "white", "weekday")
    if d == dt.date(y, 1, 6):
        return (("*",), "Epiphany", "Epiphany", "The Epiphany", "epiphany", "white", "principal feast")
    last_epiphany = Y.ash - dt.timedelta(3)
    if d < Y.epiphany1:
        return (("*",), f"Jan. {d.day}", "Epiphany", f"{wd} after the Epiphany", "epiphany", "white", "weekday")
    if d < last_epiphany:
        n = (d - Y.epiphany1).days // 7 + 1
        key = "first-sunday-after-the-epiphany" if n == 1 else f"{ORD[n].lower()}-sunday-after-the-epiphany"
        if wd == "Sunday":
            name = "The First Sunday after the Epiphany: The Baptism of our Lord" if n == 1 else f"The {ORD[n]} Sunday after the Epiphany"
            return (("Epiphany", n), wd, "Epiphany", name, key, "white" if n == 1 else "green", "sunday")
        return (("Epiphany", n), wd, "Epiphany", f"{wd} in the {ORD[n]} Week after the Epiphany", key, "green", "weekday")
    if d < Y.ash:
        if wd == "Sunday":
            return (("Epiphany", "last"), wd, "Epiphany", "The Last Sunday after the Epiphany", "last-sunday-after-the-epiphany", "white", "sunday")
        return (("Epiphany", "last"), wd, "Epiphany", f"{wd} before Ash Wednesday", "last-sunday-after-the-epiphany", "green", "weekday")
    if d == Y.ash:
        return (("*",), "Ash Wednesday", "Lent", "Ash Wednesday", "ash-wednesday", "violet", "fast")
    lent1 = Y.ash + dt.timedelta(4)
    if d < lent1:
        return (("Epiphany", "last"), wd, "Lent", f"{wd} after Ash Wednesday", "ash-wednesday", "violet", "weekday")
    palm = e - dt.timedelta(7)
    if d < palm:
        n = (d - lent1).days // 7 + 1
        key = f"{ORD[n].lower()}-sunday-in-lent"
        name = f"The {ORD[n]} Sunday in Lent" if wd == "Sunday" else f"{wd} in the {ORD[n]} Week of Lent"
        return (("Lent", n), wd, "Lent", name, key, "violet", "sunday" if wd == "Sunday" else "weekday")
    if d < e:
        names = {"Sunday": ("Palm Sunday", "The Sunday of the Passion: Palm Sunday", "sunday-of-the-passion", "red"),
                 "Monday": ("Monday", "Monday in Holy Week", "monday-in-holy-week", "red"),
                 "Tuesday": ("Tuesday", "Tuesday in Holy Week", "tuesday-in-holy-week", "red"),
                 "Wednesday": ("Wednesday", "Wednesday in Holy Week", "wednesday-in-holy-week", "red"),
                 "Thursday": ("Maundy Thursday", "Maundy Thursday", "maundy-thursday", "white"),
                 "Friday": ("Good Friday", "Good Friday", "good-friday", "black"),
                 "Saturday": ("Holy Saturday", "Holy Saturday", "holy-saturday", "black")}[wd]
        rank = "fast" if wd == "Friday" else "sunday" if wd == "Sunday" else "holy week"
        return (("Holy Week",), names[0], "Holy Week", names[1], names[2], names[3], rank)
    if d < e + dt.timedelta(7):
        if wd == "Sunday":
            return (("Easter Week",), "Easter Day", "Easter", "Easter Day: The Sunday of the Resurrection", "easter-day", "white", "principal feast")
        return (("Easter Week",), wd, "Easter", f"{wd} in Easter Week", f"{wd.lower()}-in-easter-week", "white", "easter week")
    pentecost = e + dt.timedelta(49)
    if d < pentecost:
        n = (d - e).days // 7 + 1
        if d == e + dt.timedelta(39):
            return (("*",), "Ascension Day", "Easter", "Ascension Day", "ascension-day", "white", "principal feast")
        if d > e + dt.timedelta(39) and n == 6:
            return (("Easter", 6), wd, "Easter", f"{wd} after the Ascension", "ascension-day", "white", "weekday")
        key = f"{ORD[n].lower()}-sunday-of-easter"
        name = f"The {ORD[n]} Sunday of Easter" + (": The Sunday after Ascension Day" if n == 7 else "")
        return (("Easter", n), wd, "Easter", name if wd == "Sunday" else f"{wd} in the {ORD[n]} Week of Easter", key, "white",
                "sunday" if wd == "Sunday" else "weekday")
    if d == pentecost:
        return (("*",), "The Day of Pentecost", "Easter", "The Day of Pentecost: Whitsunday", "day-of-pentecost", "red", "principal feast")
    trinity = pentecost + dt.timedelta(7)
    if d == trinity:
        return (("*",), "Trinity Sunday", "Season after Pentecost", "The First Sunday after Pentecost: Trinity Sunday",
                "first-sunday-after-pentecost", "white", "principal feast")
    sunday = sunday_on_or_before(d)
    k = proper_for(sunday)
    if wd == "Sunday":
        nth = (d - pentecost).days // 7 + 1
        words = ["", "First", "Second", "Third", "Fourth", "Fifth", "Sixth", "Seventh", "Eighth", "Ninth", "Tenth", "Eleventh",
                 "Twelfth", "Thirteenth", "Fourteenth", "Fifteenth", "Sixteenth", "Seventeenth", "Eighteenth", "Nineteenth",
                 "Twentieth", "Twenty-first", "Twenty-second", "Twenty-third", "Twenty-fourth", "Twenty-fifth", "Twenty-sixth",
                 "Twenty-seventh", "Twenty-eighth"]
        name = f"The Last Sunday after Pentecost (Proper {k})" if k == 29 else f"The {words[nth]} Sunday after Pentecost (Proper {k})"
        return (("Proper", k), wd, "Season after Pentecost", name, f"proper-{k}", "green", "sunday")
    after = "the Day of Pentecost" if sunday == pentecost else "Trinity Sunday" if sunday == trinity else None
    name = f"{wd} after {after} (Proper {k})" if after else f"{wd}, Proper {k}"
    return (("Proper", k), wd, "Season after Pentecost", name, f"proper-{k}", "red" if sunday == pentecost else "green", "weekday")


# ── Suggested canticles (Table of Canticles, pages 144-145; Rite Two numbers, Rite One in brackets) ──
def suggested_canticles(office, wd, season, feast):
    if office == "morning":
        if feast:
            return [16, 21]
        s = {"Sunday": [16, 21], "Monday": [9, 19], "Tuesday": [13, 18], "Wednesday": [11, 16], "Thursday": [8, 20],
             "Friday": [10, 18], "Saturday": [12, 19]}[wd]
        if wd == "Sunday":
            s = [{"Advent": 11, "Lent": 14, "Holy Week": 14, "Easter": 8}.get(season, 16), 16 if season in ("Advent", "Lent", "Holy Week") else 21]
        if wd in ("Wednesday", "Friday") and season in ("Lent", "Holy Week"):
            s = [14, s[1]]
        if wd == "Thursday" and season in ("Advent", "Lent", "Holy Week"):
            s = [8, 19]
        return s
    if feast:
        return [15, 17]
    s = {"Sunday": [15, 17], "Monday": [8, 17], "Tuesday": [10, 15], "Wednesday": [12, 17], "Thursday": [11, 15],
         "Friday": [13, 17], "Saturday": [9, 15]}[wd]
    if wd == "Monday" and season in ("Lent", "Holy Week"):
        s = [14, 17]
    return s


RITE_ONE = {12: 1, 13: 2, 15: 3, 16: 4, 17: 5, 20: 6, 21: 7}


# ── Assembling the offices ───────────────────────────────────────────────────────────────────
def lessons_for(entry, office, year):
    ls = entry["lessons"]
    marked = any(m for x in ls if x for _, m in [x])
    if marked:
        if office == "morning":
            return [r for x in ls if x for r, m in [x] if m in ("", "m")]
        return [r for x in ls if x for r, m in [x] if m == "e"]
    real = [x[0] for x in ls if x]
    if entry["label"].startswith("Eve of") or entry["label"] == "Christmas Eve":
        return real if office == "evening" else []
    if len(real) < 3:
        return real
    ot, epistle, gospel = real[0], real[1], real[2]
    if year == "one":
        return [ot, epistle] if office == "morning" else [gospel]
    return [ot, gospel] if office == "morning" else [epistle]


def build():
    tables = {p: parse_page(p) for p in PAGES}
    holy = parse_holy_days()
    missing = [h[0] for h in HOLY_DAYS if h[0] not in holy] + [e for e in EVES.values() if e not in holy]
    assert not missing, (missing, sorted(holy))
    calendar = parse_calendar()

    def find(year, section, label):
        for p in PAGES:
            t = tables[p][year]
            hit = t.get((section, label)) if section != ("*",) else t.get(("*", label))
            if hit:
                return hit
        raise KeyError((year, section, label))

    per_year = {y: [] for y in YEARS}
    problems = []
    for y in YEARS:
        Y = Year(y, None)
        Ynext = Year(y + 1, None)
        d = dt.date(y, 1, 1)
        while d.year == y:
            section, label, season, name, collect, colour, rank = place(d, Y)
            year = office_year(d)
            wd = WEEKDAYS[d.weekday()]
            feast = Y.holy.get(d)
            tomorrow = d + dt.timedelta(1)
            Yt = Y if tomorrow.year == y else Ynext
            tomorrow_feast = Yt.holy.get(tomorrow)
            commemoration = ""
            if not feast and rank == "weekday" and season not in ("Holy Week",):
                commemoration = calendar.get((d.month, d.day), "")
            for office in ("morning", "evening"):
                source, notes = "", []
                o_name, o_collect, o_colour, o_rank, o_feast = name, collect, colour, rank, ""
                if feast and rank not in ("principal feast",) and not (rank == "sunday" and feast[0] not in LORDS_FEASTS_OVER_SUNDAY):
                    fname, fcolour, fixed = feast
                    h = holy[fname] if fname in holy else None
                    o_feast = display_name(fname)
                    o_name, o_colour = o_feast, fcolour
                    o_rank = "feast of our Lord" if fname in LORDS_FEASTS_OVER_SUNDAY | {"The Annunciation"} else "holy day"
                    o_collect = next(k for k, md in COLLECT_DAYS.items() if md == (fixed.month, fixed.day)) if fname != "Thanksgiving Day" else "thanksgiving-day"
                    if fixed != d:
                        notes.append(f"{o_feast} ({fixed.strftime('%B')} {fixed.day}) is transferred to this day.")
                    if fname == "Thanksgiving Day":
                        o_rank = "holy day"
                    part = h[office] if h else None
                    if part:
                        psalms, lessons = part["psalms"], part["lessons"]
                        source = "Holy Days"
                if not source:
                    entry = None
                    if d.month == 12 and d.day == 24:
                        entry = find(year, ("*",), "Christmas Eve") if office == "evening" else (
                            find(year, ("Advent", 4), "Sunday") if wd == "Sunday" else find(year, ("*",), "Dec. 24"))
                    else:
                        entry = find(year, section, label)
                    # The Eve of a feast gives this evening's office — unless this day is itself a feast or a Sunday.
                    if office == "evening" and (rank == "weekday" and not feast or not entry["psalms"][1]):
                        eve = eve_label(tomorrow, Yt, tomorrow_feast)
                        if eve:
                            try:
                                entry = find(office_year(tomorrow), ("*",), eve) if not eve.startswith("HOLY:") else None
                                if eve.startswith("HOLY:"):
                                    hd = holy[eve[5:]]
                                    psalms, lessons, source = hd["evening"]["psalms"], hd["evening"]["lessons"], "Holy Days"
                                    notes.append(f"The Eve of {display_name(eve[5:].replace('Eve of ', ''))}.")
                            except KeyError:
                                problems.append((d, eve))
                    if not source:
                        mp, ep = entry["psalms"]
                        psalms = mp if office == "morning" else ep
                        if office == "evening" and wd == "Saturday" and entry.get("saturdayEvening"):
                            sat = re.search(r"use Psalms? ([\d ,and]+) at Evening", entry["saturdayEvening"])
                            if sat:
                                psalms = re.sub(r"\s+and\s+", ", ", sat.group(1).strip())
                                notes.append(entry["saturdayEvening"])
                        if office == "morning" and not psalms:
                            psalms = ""
                        lessons = lessons_for(entry, office, year if not entry["label"].startswith("Eve") else office_year(tomorrow))
                        source = f"Year {year.title()}"
                        if entry["label"].startswith("Eve of") or entry["label"] == "Christmas Eve":
                            if office == "evening" and d.month == 12 and d.day == 24:
                                pass
                            elif office == "evening":
                                notes.append(f"{entry['label']}.")
                if not psalms and not lessons:
                    problems.append((d, office, "empty"))
                cites = [cite(re.split(r";\s*or\s+", l)[0]) for l in lessons]
                nums = psalm_numbers(psalms)
                rel = [{"predicate": "PSALM", "to": {"type": "Passage", "osis": f"Ps.{n}"}} for n in nums]
                for c in cites:
                    for o in passage_osis(c):
                        rel.append({"predicate": "LESSON", "to": {"type": "Passage", "osis": o}})
                rel.append({"predicate": "COLLECT", "to": {"type": "Collect", "key": o_collect}})
                canticles = suggested_canticles(office, wd, season, bool(o_feast) or o_rank == "principal feast")
                rel += [{"predicate": "CANTICLE", "to": {"type": "Canticle", "key": f"canticle-{n}"}} for n in canticles]
                per_year[y].append({"type": "OfficeDay", "data": {
                    "key": f"{d.isoformat()}/{office}", "date": d.isoformat(), "office": office, "weekday": wd,
                    "name": o_name, "feast": o_feast, "commemoration": commemoration if not o_feast else "",
                    "season": season, "colour": o_colour, "rank": o_rank, "lectionaryYear": year,
                    "psalms": psalms, "psalmPassages": [f"Psalms {n}" for n in nums],
                    "lessons": lessons,
                    "lessonPassages": [f"{c['book']} {n}" for c in cites if c and c["osis"] for n in c["chapters"]],
                    "collect": o_collect, "canticles": [f"canticle-{n}" for n in canticles],
                    "canticlesRiteOne": [f"canticle-{RITE_ONE[n]}" if n in RITE_ONE else "" for n in canticles],
                    "source": source, "note": " ".join(notes),
                }, "relations": rel})
            d += dt.timedelta(1)
    assert not problems, problems[:20]
    for y in YEARS:
        write(f"anglican-office-{y}.yml", f"""
# The Daily Office for {y}: Morning and Evening Prayer for each day — the day's place in the church
# year, the psalms and lessons the Daily Office Lectionary appoints, the collect, and the canticles the
# Prayer Book suggests. An office's psalms are each the PSALM chapter, its lessons LESSON chapters (a
# lesson from the Apocrypha is cited but joins to none: the realm's Bible has no Apocrypha), and it is
# prayed with its COLLECT and CANTICLEs. The colour is custom; the Prayer Book appoints none.
# Source: The Book of Common Prayer (1979), the Episcopal Church — public domain;
# https://www.bcponline.org/DOLectionary/ . Generated by scripts/anglican/build_office.py.
""", per_year[y])


def eve_label(tomorrow, Yt, tomorrow_feast):
    """The Eve whose evening office this is, if tomorrow is a feast the tables give an Eve for."""
    e = Yt.easter
    if tomorrow == dt.date(tomorrow.year, 1, 1):
        return "Eve of Holy Name"
    if tomorrow == dt.date(tomorrow.year, 1, 6):
        return "Eve of Epiphany"
    if tomorrow == Yt.epiphany1:
        return "Eve of 1 Epiphany"
    if tomorrow == e + dt.timedelta(39):
        return "Eve of Ascension"
    if tomorrow == e + dt.timedelta(49):
        return "Eve of Pentecost"
    if tomorrow == e + dt.timedelta(56):
        return "Eve of Trinity Sunday"
    if tomorrow_feast and tomorrow_feast[0] in EVES and tomorrow.weekday() != 6:
        return "HOLY:" + EVES[tomorrow_feast[0]]
    return None


COLLECT_DAYS = {}


def load_collect_days():
    import yaml
    from common import REF
    import os
    for r in yaml.safe_load(open(os.path.join(REF, "anglican-collects.yml"))):
        md = r["data"]["monthDay"]
        if r["data"]["kind"] == "holy day" and md:
            COLLECT_DAYS[r["data"]["key"]] = (int(md[:2]), int(md[3:]))


if __name__ == "__main__":
    load_collect_days()
    build()
