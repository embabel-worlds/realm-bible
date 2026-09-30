# realm-bible

The Bible as a queryable graph: search verses in the King James Version (default) or the World
English Bible (modern), read a chapter, compare a verse across seven translations, and find the
people of the Bible, the verses that mention them, and their parents.

## Shape

```
Book ◀─IN─ Passage ◀─IN─ Verse ─MENTIONS─▶ BiblePerson ─FATHER/MOTHER─▶ BiblePerson
                            └─RENDERED─▶ AsvVerse · BbeVerse · DarbyVerse · DraVerse · YltVerse
BibleNameQuery {name} ─NAMED─▶ BiblePerson
```

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

## Attribution

- Theographic Bible Metadata, by Robert Rouse — CC BY-SA 4.0,
  https://github.com/robertrouse/theographic-bible-metadata. The Book, Passage and Verse reference
  data, the KJV text as Theographic publishes it, and all person data derive from it, and are
  shared under the same licence.
- World English Bible — public domain, via https://ebible.org.
- ASV, BBE, Darby, Douay-Rheims and YLT — public domain, served by https://bible-api.com.
- Easton's Bible Dictionary (1897), quoted in `BiblePerson.dictionary` — public domain.
