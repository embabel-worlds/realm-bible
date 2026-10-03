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

## Jonathon

`personalities/jonathon/` and `focuses/bible.yml` — the realm ships a speaker. Jonathon is a
pastor: he listens, he opens the text rather than talking about it, he wants the person he is
talking to known and he wants them to come to faith, and he says so once rather than pushing.

```
/focus bible
```

The focus binds the chat to `realm-bible` alone, so Jonathon reaches scripture, the people in it
and the translations, and no other realm's tools — a pastor who can also read your email is a
different and worse idea. `builtins: true` is kept deliberately: he needs `view_run` to read a
verse, and `memory_save` / `memory_search` to remember a person between conversations. Add
`realm-research` to the focus's `realms` to let him reach `TodaysHeadlines` and `PassagesForStory`.

Two rules in his prompt are load-bearing. Every word of scripture comes from a `view_run` call and
is named with its translation — he never quotes from memory, because misquoting scripture to make a
point is the one failure with no excuse. And a disclosure of self-harm, abuse or danger drops the
register entirely for emergency services and a crisis line: he is not a counsellor, and faith is
not the treatment.

## The Catholic year, the saints, and devotions

Stored, so they answer at once:

| Data | Source | View |
|---|---|---|
| `LiturgicalDay`, `Celebration` — every day 2025–2030 of the General Roman Calendar: celebrations by rank (optional memorials kept), colour, season, lectionary cycles, holy days of obligation | computed by [romcal](https://github.com/romcal/romcal) (MIT), `scripts/calendar/` | `TodayInTheChurch`, `FeastsInRange` |
| `RosaryMystery`, `RosaryDay` — the twenty mysteries, each with its Scripture (TOLD_IN the Passage) and fruit, and the set for each weekday | the Church's practice (*Rosarium Virginis Mariae*, 2002) | `RosaryToday` |
| `Prayer` — Our Father, Hail Mary, Glory Be, Hail Holy Queen, the Angelus, the Memorare… | traditional English forms, public domain | `Prayers` |
| `CatechismEntry` — the Baltimore Catechism No. 2, question by question | Project Gutenberg #14552, public domain | `CatechismLesson`, `CatechismSearch` |
| `CccTopic` — ~80 topics, feasts and Rosary mysteries mapped to paragraphs of the Catechism of the Catholic Church, linked to the official text on vatican.va | paragraph numbers only — the CCC's text is copyright and not carried | `CatechismOnTopic` |
| `CalendarSaint` — each calendar saint's Wikidata entity; `ScriptureSaint` — saints who are people of Scripture, matched to Theographic; `Country` — ISO 3166 codes to Wikidata | Wikidata (CC0), matched and reviewed in `scripts/saints/` | — |

Fetched live, cached a week:

| Data | Source | View |
|---|---|---|
| `SaintCard` — dates; birth, death and burial places with coordinates; image; order; canonization | Wikidata (CC0) | `SaintsOfTheDay`, `SaintLife` |
| `SaintLife` — the opening of the saint's Wikipedia article | Wikipedia (CC BY-SA 4.0 — shown with its link, never stored) | `SaintLife` |
| `SaintPatronage` — what the saint is patron of | Wikidata P417, churches excluded | `SaintPatronOf` |
| `CountrySaint` — the saints and blessed of a country, by citizenship or birthplace | Wikidata (CC0) | `SaintsOfCountry` |

`SaintsInScripture` joins the two worlds: the apostles, the Holy Family, the women of Bethany and the
rest, with the verses that name them and their feasts.

Things to know:

- **The universal calendar only.** A country's own calendar — its patron, a holy day a bishops'
  conference moves to Sunday — is not applied, and a Sunday outranks most saints (St Francis falls on
  the 27th Sunday of Ordinary Time in 2026).
- **A saint is matched once, by hand where it matters.** Wikidata's search finds churches and
  paintings as readily as saints; `scripts/saints/calendar-saints.json` records each match and whether
  it was searched or curated. romcal names both apostles James `james_apostle`; the one kept with
  Philip on 3 May is renamed `james_the_less_apostle`.
- **Catechisms are public-domain texts only.** The Baltimore Catechism's source is a later printing
  that revised one answer (No. 257, the Communion fast) to then-current discipline; that answer is
  withheld rather than passed off as the 1885 text. The Catechism of the Catholic Church is linked,
  never quoted.
- **Rebuilding:** `cd scripts/calendar && npm ci && node build.mjs`; `python scripts/devotions/crawl_ccc.py`
  then `python scripts/devotions/build_devotions.py`; `python scripts/saints/build_saints.py`. Downloads
  are cached under `data/source/` (git-ignored).

## The Daily Office — the Anglican edition

`apps/anglican.html` is Morning and Evening Prayer for any day of 2025–2030 by the Episcopal Church's
*Book of Common Prayer* (1979). Everything is stored, so it answers at once:

| Data | Source | View |
|---|---|---|
| `OfficeDay` — each morning and evening: the day in the church year, any Holy Day kept, season, customary colour, lectionary year, the psalms (PSALM the chapter) and lessons (LESSON the chapters), the COLLECT and the suggested CANTICLEs | computed from the Prayer Book's own tables and rules, `scripts/anglican/build_office.py` | `DailyOffice`, `OfficePsalmChapters`, `ChurchYear`, `CollectOfTheDay` |
| `Collect` — the collects of the church year and the Holy Days, Rite One and Rite Two | the 1979 BCP | `Collects`, `CollectOfTheDay` |
| `Canticle` — the twenty-one canticles of the Office (FROM their chapter) | the 1979 BCP | `Canticles` |
| `BcpPsalm` — the Prayer Book's own Psalter (SAME_AS the chapter of Psalms) | the 1979 BCP | `PsalterPsalm` |
| `BcpPrayer` — the seventy Prayers and eleven Thanksgivings | the 1979 BCP | `PrayerBookPrayers` |
| `CatechismEntry` — An Outline of the Faith (`bcp-1979`) and the Church Catechism of 1662 (`church-catechism`) | the 1979 BCP; the 1928 US BCP's American form of the 1662 Catechism | `OutlineOfTheFaith`, `CatechismLesson`, `CatechismSearch` |
| `ArticleOfReligion` — the Thirty-Nine Articles as established in 1801, with the 1571 text where it differs, PROVED_BY the chapters an 1877 catechism of the Articles cites | the 1979 BCP's Historical Documents; *A Catechism of the Thirty-Nine Articles … with Scripture Proofs* (1877), references only | `ArticlesOfReligion`, `ArticlesSearch`, `ArticleProofChapters` |

Things to know:

- **The Prayer Book's rules, applied at build time.** Year One of the lectionary begins at Advent before
  an odd year; of a day's three readings the Gospel goes to the evening in Year One and the morning in
  Year Two; Propers after Pentecost go by the Sunday closest to their date; Holy Days move off Sundays
  and out of Holy Week and Easter Week; Eves give the evening before a feast. Where the Prayer Book
  leaves a choice to the officiant (re-ordering around a feast, the alternative psalms), the tables'
  appointment is shown.
- **Colours are custom.** The Prayer Book appoints none; Advent is given as blue, the common Episcopal
  use.
- **No 1662 texts, no lectionaries under copyright.** The English 1662 Prayer Book is Crown property in
  the United Kingdom, so its collects and offices are not carried; the 1662 Catechism comes from the
  American 1928 book instead. The Revised Common Lectionary and *Lesser Feasts and Fasts* are copyright:
  the calendar's commemorations are named, their propers are not given.
- **No Apocrypha.** The realm's Bible is the Protestant canon, so a lesson from Ecclesiasticus or Wisdom
  is cited but joins to no chapter.
- **Rebuilding:** `python scripts/anglican/build_texts.py` then `python scripts/anglican/build_office.py`.
  Downloads are cached under `data/source/anglican/` (git-ignored).

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
- The General Roman Calendar data is computed by romcal (MIT, https://github.com/romcal/romcal).
- The Baltimore Catechism No. 2 (1885), via Project Gutenberg eBook #14552 — public domain.
- Wikidata (saints, places, countries) — CC0. Wikipedia summaries — CC BY-SA 4.0, fetched live and
  shown with their link.
- The Catechism of the Catholic Church is linked at https://www.vatican.va/archive/ENG0015/ — its text
  is not reproduced.
- The Book of Common Prayer (1979) of the Episcopal Church — public domain ("the U S Book of Common
  Prayer is not and never has been under copyright", the Episcopal Church), via https://www.bcponline.org.
- The Church Catechism, from the Episcopal Church's Book of Common Prayer (1928) — public domain in the
  United States, via http://justus.anglican.org/resources/bcp/1928/.
- *A Catechism of the Thirty-Nine Articles … with Scripture Proofs*, by J. W. (2nd ed., 1877) — public
  domain; its Scripture references only, via https://newscriptorium.com.
