#!/bin/sh
# Ground truth for realm-bible, against the sources it was built from and the ones it reads live.
#
#   L1  every view answers BY NAME on its defaults, and is not empty unless its default cannot have
#       rows (a required reference left empty) or it rests on something outside the realm: the news
#       strip needs realm-research and a search key; the two agentic searches need the chapter
#       documents and a model — those are held to answering, and say what they returned
#   L2  the graph against its sources, fetched fresh: every KJV verse's text and `people` against
#       Theographic's Verses.csv, every WEB verse against eBible's text, book by book, exactly; the
#       holy book's counts; the people against Theographic's People.csv — everyone, the women, one
#       person's father, verse count and children
#   L3  cost and pushdown: one person by id or by name is one read of the source file; a filter on
#       `gender` is pushed into that read and the answer equals the file's count; one verse in the
#       five fetched translations is at most five calls cold
#
# Keyless: every source is public. The news view's search key is realm-research's, not this realm's.
#
#   APPLIANCE=http://127.0.0.1:11043 AUTH=user:pass sh tests/verify.sh
#
# The last line on success is exactly `ALL CHECKS PASS`; any failure exits non-zero. The browser
# tests (tests/*.live.mjs, tests/views.smoke.mjs) drive the apps and are run separately.
set -e
AUTHCFG=$(mktemp); trap 'rm -f "$AUTHCFG"' EXIT
if [ -n "${TOKEN:-}" ]; then printf 'header = "Authorization: Bearer %s"\n' "$TOKEN" > "$AUTHCFG"
else printf 'user = "%s"\n' "${AUTH:?set AUTH (user:pass) or TOKEN}" > "$AUTHCFG"; fi
APPLIANCE="${APPLIANCE:-http://127.0.0.1:11043}"
BATTERY_LIB="$(dirname "$0")/lib" APPLIANCE="$APPLIANCE" AUTHCFG="$AUTHCFG" python3 - "$(dirname "$0")/.." <<'PY'
import csv, glob, io, json, os, re, subprocess, sys, urllib.request, zipfile, yaml
base, auth, realm = os.environ["APPLIANCE"], os.environ["AUTHCFG"], sys.argv[1]
THEOGRAPHIC = "https://raw.githubusercontent.com/robertrouse/theographic-bible-metadata/master/CSV/{}.csv"
WEB_VPL = "https://ebible.org/Scriptures/engwebp_vpl.zip"
fail = 0

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "realm-bible tests/verify.sh"})
    return urllib.request.urlopen(req, timeout=180).read()
def table(name):
    return list(csv.DictReader(io.StringIO(get(THEOGRAPHIC.format(name)).decode("utf-8-sig"))))
def post(path, body):
    out = subprocess.run(["curl", "-s", "--max-time", "900", "-K", auth, "-X", "POST", base + path,
                          "-H", "Content-Type: application/json", "-d", json.dumps(body)],
                         capture_output=True, text=True).stdout
    try:
        return json.loads(out, strict=False)
    except ValueError:
        return {"error": "not JSON: " + out[:200]}
# A figure is only this realm's when the engine says the answer is whole. short() is the battery
# library's (tests/lib, pinned from embabel-worlds/realm-spec): None when whole, else the line that
# stands in for the figure, "REFUSED: <why>" or "PARTIAL <figure>: <the engine's reason>".
import os as _os, sys as _sys
_sys.path.insert(0, _os.environ["BATTERY_LIB"])
from short import short  # noqa: E402
def kg_full(cypher, fresh=False):
    body = {"cypher": cypher}
    if fresh: body["ai"] = {"fresh": True}
    r = post("/api/v1/admin/kg/execute", body)
    if fresh and (r.get("error") or r.get("code")):
        print("  note a cold read was refused (%s); read warm instead" % str(r.get("message") or r.get("error"))[:300])
        r = post("/api/v1/admin/kg/execute", {"cypher": cypher})
    if r.get("error") or r.get("code"):
        raise SystemExit("  FAIL query REFUSED: %s\n    %s" % (str(r.get("error") or r.get("message") or r)[:400], cypher))
    # A short count stops the battery as a refusal does: every check after it would read the same gap.
    rows = r.get("rows") or []
    s = short(r, rows[0]["n"] if len(rows) == 1 and "n" in rows[0] else "%d rows" % len(rows))
    if s:
        raise SystemExit("  FAIL query %s\n    %s" % (s, cypher))
    return r
def kg(cypher): return kg_full(cypher).get("rows") or []
def view(name, args=None, whole=True):
    r = post("/api/v1/views/%s/invoke" % name, {"args": args or {}})
    # Rows a view marks short are not its answer, so no check counts them. L1 asks with whole=False
    # because it reports each view's verdict itself and goes on to the next.
    s = whole and short(r, len(r.get("data") or []))
    if s:
        raise SystemExit("  FAIL view %s %s: %s" % (name, json.dumps(args or {}), s))
    return r
def check(what, want, got):
    global fail
    if want == got: print("  ok   %s = %s" % (what, got if len(str(got)) < 80 else str(got)[:77] + "..."))
    else: print("  FAIL %s: expected %s, got %s" % (what, str(want)[:300], str(got)[:300])); fail = 1
def at_most(what, bound, got):
    global fail
    if isinstance(got, int) and got <= bound: print("  ok   %s: %d call(s), bound %d" % (what, got, bound))
    else: print("  FAIL %s: %s call(s), bound %d" % (what, got, bound)); fail = 1
def calls(r):
    m = r.get("metrics") or {}
    for v in (r.get("apiCalls"), m.get("externalCalls"), m.get("apiCalls")):
        if isinstance(v, int): return v
    return "not reported (envelope keys: %s)" % sorted(r)

# The stored reference is written in the background after the realm reports active, and a view read
# before it is done answers from a half-written graph: a missing node is no row, a missing edge a
# relationship the schema does not have yet. Nothing below is meaningful until every stored type
# holds what reference/ declares, so wait for exactly that, type by type.
import time
stored = {}
for f in sorted(glob.glob(os.path.join(realm, "reference", "*.yml"))):
    for rec in yaml.safe_load(open(f)) or []:
        if isinstance(rec, dict) and rec.get("type"): stored[rec["type"]] = stored.get(rec["type"], 0) + 1
deadline = time.time() + 1800
while True:
    missing = {t: (kg("MATCH (x:%s) RETURN count(x) AS n" % t) or [{"n": 0}])[0]["n"] for t in stored}
    missing = {t: "%d/%d" % (got, stored[t]) for t, got in missing.items() if got != stored[t]}
    if not missing: break
    if time.time() > deadline:
        print("  FAIL the reference seed was still short after 30 minutes: %s" % missing); fail = 1; break
    print("  wait the reference seed is still writing: %s" % ", ".join("%s %s" % kv for kv in sorted(missing.items())[:8]))
    time.sleep(30)

print("== L1: every view answers by name ==")
EMPTY_BY_DESIGN = set()
OUTSIDE = {"SearchPassages": "needs the chapter documents and a model",
           "PassagesForStory": "needs the chapter documents and a model; none is a real answer"}
for f in sorted(glob.glob(os.path.join(realm, "views", "*.yml"))):
    for v in yaml.safe_load(open(f)):
        n = v["name"]
        r = view(n, whole=False)
        rows = r.get("data") or []
        if n in OUTSIDE and (r.get("status") != "SUCCEEDED" or not rows or short(r, len(rows))):
            print("  note %-28s %s, %d rows — %s" % (n, short(r, len(rows)) or r.get("status"), len(rows), OUTSIDE[n]))
        elif r.get("status") != "SUCCEEDED":
            print("  FAIL %s: %s %s" % (n, r.get("status"), str(r.get("error") or r)[:600])); fail = 1
            if "VIEW_QUERY_INVALID" in json.dumps(r):
                # The view's refusal says only that the query is invalid; the same query run directly,
                # with its defaults written in, names the defect.
                q = v.get("cypher", "")
                for pn, spec in sorted((v.get("params") or {}).items(), key=lambda kv: -len(kv[0])):
                    q = q.replace("$" + pn, json.dumps(spec.get("default")).replace('"', "'"))
                d = post("/api/v1/admin/kg/execute", {"cypher": q})
                print("       why: %s" % str(d.get("error") or d.get("message") or "the query ran directly: %d rows" % len(d.get("rows") or []))[:900])
        elif short(r, len(rows)):
            print("  FAIL %s: %s" % (n, short(r, len(rows)))); fail = 1
        elif not rows and n not in EMPTY_BY_DESIGN:
            print("  FAIL %s answered no rows on its defaults" % n); fail = 1
        else:
            print("  ok   %-28s %d rows" % (n, len(rows)))
        for w in r.get("warnings") or []:
            print("       warning: %s" % str(w)[:300])

print("== L3: cost and pushdown, read cold ==")
people = table("People")
r = kg_full("MATCH (p:BiblePerson {personLookup: 'jezebel_1605'}) RETURN p.name AS name", fresh=True)
check("one person by id", [{"name": "Jezebel"}], r.get("rows"))
at_most("  ...read by id", 1, calls(r))
r = kg_full("MATCH (p:BiblePerson {name: 'Zechariah'}) RETURN count(p) AS n", fresh=True)
check("every Zechariah by name = the file", sum(1 for p in people if p["name"].lower() == "zechariah"), (r.get("rows") or [{}])[0].get("n"))
at_most("  ...read by name", 1, calls(r))
r = kg_full("MATCH (:BibleRoll)-[:PERSON]->(p:BiblePerson) WHERE p.gender = 'Female' RETURN count(p) AS n", fresh=True)
check("the women, gender pushed into the read = the file", sum(1 for p in people if p["gender"] == "Female"), (r.get("rows") or [{}])[0].get("n"))
at_most("  ...one read of the file", 1, calls(r))
r = view("CompareTranslations", {"ref": "John 11:35"})
check("CompareTranslations John 11:35: six translations", 6, len(r.get("data") or []))
if len(r.get("data") or []) != 7:
    print("       got: %s; warnings: %s" % ([x.get("translation") for x in r.get("data") or []], str(r.get("warnings"))[:400]))
at_most("  ...at most five fetched", 5, calls(r))

print("== L2: the graph against its sources ==")
# The stored reference loaded whole, type by type: every view over stored data stands on it.
for t, n in sorted(stored.items()):
    check("stored %s = reference/" % t, n, kg("MATCH (x:%s) RETURN count(x) AS n" % t)[0]["n"])
verses = table("Verses")
web = {}
books = sorted(table("Books"), key=lambda b: int(b["bookOrder"]))
vpl = zipfile.ZipFile(io.BytesIO(get(WEB_VPL))).read("engwebp_vpl.txt").decode("utf-8")
order, by = [], {}
for line in vpl.splitlines():
    m = re.match(r"^(\w{3}) (\d+):(\d+) (.*)$", line)
    if m:
        if m.group(1) not in order: order.append(m.group(1))
        by[(m.group(1), int(m.group(2)), int(m.group(3)))] = m.group(4).strip()
osis_of = {c: b["osisName"] for c, b in zip(order, books)}
web = {"%s.%d.%d" % (osis_of[c], ch, v): t for (c, ch, v), t in by.items()}
check("holy book's counts = Theographic", [{"chapters": len(table("Chapters")), "verses": len(verses)}],
      kg("MATCH (h:BibleCanon) RETURN h.chapterCount AS chapters, h.verseCount AS verses"))
check("verses stored = Verses.csv", len(verses), kg("MATCH (v:BibleVerse) RETURN count(v) AS n")[0]["n"])
want = {}
for v in verses:
    want.setdefault(v["book"], {})[v["osisRef"]] = (v["verseText"].strip(), [x for x in (v["people"] or "").split(",") if x], web.get(v["osisRef"]))
bad = {"kjv": [], "people": [], "web": [], "count": []}
for b in books:
    rows = {r["o"]: (r["t"], r["p"] or [], r["w"]) for r in
            kg("MATCH (v:BibleVerse {book: '%s'}) RETURN v.osis AS o, v.text AS t, v.people AS p, v.web AS w" % b["osisName"])}
    w = want.get(b["osisName"], {})
    if len(rows) != len(w): bad["count"].append(b["osisName"])
    for o, (t, p, wt) in w.items():
        g = rows.get(o, (None, None, None))
        if g[0] != t: bad["kjv"].append(o)
        if sorted(g[1] or []) != sorted(p): bad["people"].append(o)
        if g[2] != wt: bad["web"].append(o)
for k, ks in bad.items():
    check("every book's verses: %s, exactly" % k, [], ks[:5])
roll = kg("MATCH (:BibleRoll)-[:PERSON]->(p:BiblePerson) RETURN count(p) AS n, count(DISTINCT p.personLookup) AS ids")[0]
check("everyone on the roll = People.csv", [len(people), len(people)], [roll["n"], roll["ids"]])
jez = next(p for p in people if p["slug"] == "jezebel_1605")
r = kg("MATCH (p:BiblePerson {personLookup: 'jezebel_1605'}) OPTIONAL MATCH (p)-[:FATHER]->(f:BiblePerson) "
       "RETURN p.verseCount AS verses, f.personLookup AS father")
check("Jezebel's verse count (an int) and father = the file", [{"verses": int(jez["verseCount"]), "father": jez["father"] or None}], r)
david = next(p for p in people if p["slug"] == "david_994")
kids = sorted(c.strip() for c in david["children"].split(",") if c.strip())
r = kg("MATCH (:BiblePerson {personLookup: 'david_994'})-[:CHILD]->(c:BiblePerson) RETURN c.personLookup AS id ORDER BY id")
check("David's children = the file (%d)" % len(kids), kids, [x["id"] for x in r])

if fail: print("FAILED"); sys.exit(1)
print("ALL CHECKS PASS")
PY
