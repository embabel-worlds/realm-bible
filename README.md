# realm-bible

> **Experimental.** It relies on engine features from October 2026 — finding a person by name,
> walking a family tree in reverse and through list-valued keys, and DERIVE demands planned like
> queries. On an older host those queries are refused. Querying the `Rendering` parent label (every
> translation at once) awaits a further engine fix; the concrete translation labels work everywhere.

The Bible as a queryable graph: search verses in the King James Version (default) or the World
English Bible (modern), read a chapter, compare a verse across seven translations, and find the
people of the Bible, the verses that mention them, and their parents.

## Shape

```
Book ◀─IN─ Passage ◀─IN─ Verse ─MENTIONS─▶ BiblePerson ─FATHER/MOTHER/CHILD─▶ BiblePerson
                            └─RENDERED─▶ Rendering: AsvVerse · BbeVerse · DarbyVerse · DraVerse · YltVerse
BibleNameQuery {name}        ─NAMED───▶ BiblePerson
BibleIdQuery {personLookup}  ─WITH_ID─▶ BiblePerson
```

A person can be found directly — `MATCH (p:BiblePerson {name: 'Moses'})` — and walked either way:
`(p)-[:FATHER|MOTHER*1..30]->(a)` for ancestors, `(p)<-[:FATHER|MOTHER*]-(d)` or `(p)-[:CHILD*]->(d)`
for descendants. FATHER and MOTHER are declared in both directions, each from the end that holds the
key, so a reverse walk is an exact lookup by the child's own record, not a guess.

| | Stored or fetched | Source |
|---|---|---|
| Book, Passage (= chapter), Verse with KJV `text` | stored, `reference/` | Theographic Bible Metadata |
| Verse `web` (World English Bible) | stored, `reference/` | eBible.org |
| BiblePerson | fetched, tabular producer over `People.csv` | Theographic Bible Metadata |
| Asv/Bbe/Darby/Dra/YltVerse | fetched, one verse per call | bible-api.com |

Two translations are stored because search has to scan text, and a producer cannot be scanned.
The other five are fetched because nobody searches the Darby for a word.

## Search by meaning

`sources.yml` declares the Bible as searchable documents as well as a graph — one document per
chapter, in both stored translations:

| Source | Trigger | Documents |
|---|---|---|
| `bible-kjv` | on-install | 1,189 chapters, `bible://kjv/<osis>` |
| `bible-web` | manual (`realm_sync_documents`) | 1,189 chapters, `bible://web/<osis>` |
| `about-the-translations` | on-install | two Wikipedia pages, fetched |

A document's uri ends in its passage's OSIS reference (`bible://web/Judg.4` is `Passage {osis:'Judg.4'}`),
so a search hit joins straight back to the graph.

**Search the WEB, show the KJV.** Measured on the same query — *"a woman kills a sleeping enemy
general by driving a tent peg through his head"* — the WEB corpus ranks Judges 4 and 5 first and
second; the KJV corpus, in seventeenth-century English, misses both in its top five. A reader asking
in modern English should be searched against modern English, and can then be shown any translation.

Needs an embedding model configured on the appliance; without one, documents ingest but search by
meaning does not work.

## Derived knowledge — DERIVE rule sets

`rules/` holds rule sets the engine evaluates to a fixpoint whenever a query names their label. Each
has a view that names it, so the conclusions reach every surface with no client work.

| Rule set | Concludes | View |
|---|---|---|
| `tribes.yml` | `TribeMember {tribe}` — a son of Israel founds a tribe; descendants inherit it through the father | `TribeOf`, `TribeCensus` |
| `progenitors.yml` | `Progenitor {descendants}` — descendant counts summed up the tree | `GreatestHouses` |
| `generations.yml` | `Generation {fromAdam}` — generations from Adam along the longest male line | `GenerationFromAdam` |
| `parallels.yml` | `(a)-[:PARALLELS {shared}]->(b)` — chapters in different books sharing a cast | `ParallelTellings` |
| `tribal-chapters.yml` | `TribalChapter {tribe, tribalCast}` — a chapter whose cast is mostly one tribe; stacked on `tribes` | `TribalChapters` |

The genealogy is fetched, not stored, so the genealogical sets declare a `requires:` demand that walks
the family tree before any rule runs. The numbers check against Scripture: Noah 9 generations from
Adam (Genesis 5), David 13 after Abraham (Matthew 1), Moses and Aaron of Levi, David of Judah; the
parallels find Ezra 2 ↔ Nehemiah 7, 2 Samuel 23 ↔ 1 Chronicles 11 and Mark 3 ↔ Matthew 10.

## The app

`apps/scripture-search.html` — search for a passage the way you remember it ("bears eat boys who
mocked a prophet" finds 2 Kings 2), read it in KJV or WEB, see who is in it, compare a verse across
seven translations, and find Scripture that tells the same kind of event as today's news (needs
realm-research with a Brave key). Search is agentic retrieval over the WEB chapters. The page's own
"How it works" shows every query it runs.

`tests/scripture-search.live.mjs` drives the app in a real browser against a live appliance:

```bash
APPLIANCE_URL=http://localhost:11043 APPLIANCE_USER=… APPLIANCE_PASSWORD=… node tests/scripture-search.live.mjs
```

## Things to know

- **A Passage is a chapter.** Pericope boundaries differ between publishers; chapters are the
  division every source shares.
- **A name is not a person.** `BiblePerson`'s identity is Theographic's id (`jezebel_1605`).
  `PeopleNamed` returns every bearer of a name.
- **Theographic is unfinished.** Many records are `status: wip`, and some tags are wrong
  (Jezebel is filed under "Genealogy of Jesus"). Years are scholarly estimates. Views show the
  status.
- **bible-api is rate-limited** (about 15 requests per 30 seconds) and a remote producer cannot be
  paced, so only `CompareTranslations` reaches it, one verse at a time. Fetched verses are cached
  forever.
- **Young's Literal is New Testament only** on bible-api. An Old Testament verse has no YLT row.
- **Romans 16:26–27 have no WEB text**; the WEB numbers the end of Romans differently.
- **The Douay-Rheims arrives in KJV numbering**: bible-api maps it, so its "Psalm 23" is the
  Vulgate's Psalm 22.

## Rebuilding the reference data

```bash
pip install pyyaml
python scripts/build_reference.py     # downloads the sources into data/source/, writes reference/
```

The first load of the realm seeds ~32,000 records, which takes a few minutes; later loads skip the
seed while the reference files are unchanged.

## Licence and attribution

The realm's own files are GPL-3.0 (`LICENSE`). The reference data and person data are shared under
CC BY-SA 4.0, as their source requires:

- Theographic Bible Metadata, by Robert Rouse — CC BY-SA 4.0,
  https://github.com/robertrouse/theographic-bible-metadata. The Book, Passage and Verse reference
  data, the KJV text as Theographic publishes it, and all person data derive from it, and are
  shared under the same licence.
- World English Bible — public domain, via https://ebible.org.
- ASV, BBE, Darby, Douay-Rheims and YLT — public domain, served by https://bible-api.com.
- Easton's Bible Dictionary (1897), quoted in `BiblePerson.dictionary` — public domain.
