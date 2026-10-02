"""Index which page of the Vatican's online Catechism of the Catholic Church holds each paragraph.

The realm carries NO text of the Catechism of the Catholic Church — it is under copyright. It carries
paragraph numbers (facts) and links to the official text the Holy See publishes at
https://www.vatican.va/archive/ENG0015/. That site has one page per section and no per-paragraph
anchor, so a link to "CCC 1324" has to name the page holding paragraph 1324: this script finds it.
Pages are cached under data/source/ccc/ so a rerun asks nothing of the server.

    python scripts/devotions/crawl_ccc.py      # writes data/source/ccc/paragraph-pages.json
"""
import json, os, re, time, urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
CACHE = os.path.join(ROOT, 'data', 'source', 'ccc')
BASE = 'https://www.vatican.va/archive/ENG0015/'
UA = {'User-Agent': 'realm-bible-build/0.1 (https://github.com/embabel-worlds/realm-bible)'}


def page(name):
    path = os.path.join(CACHE, 'pages', name)
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        for attempt in range(5):
            try:
                with urllib.request.urlopen(urllib.request.Request(BASE + name, headers=UA), timeout=60) as r:
                    open(path, 'wb').write(r.read())
                break
            except Exception as e:
                wait = 2 ** attempt
                print(f'  {name}: {e} — retry in {wait}s', flush=True)
                time.sleep(wait)
        time.sleep(0.4)
    return open(path, encoding='latin-1').read()


index = page('_INDEX.HTM')
names = []
for href, label in re.findall(r'(?i)href\s*=\s*"?(__P[0-9A-Z]+\.HTM)"?[^>]*>(.*?)</a>', index, re.S):
    if href not in [n for n, _ in names]:
        names.append((href, re.sub(r'\s+', ' ', re.sub('<[^>]+>', '', label)).strip()))
print(len(names), 'section pages', flush=True)
out = {}
for i, (name, title) in enumerate(names):
    nums = [int(n) for n in re.findall(r'<p class=MsoNormal>(?:<[^>]+>)*\s*(\d{1,4})\b', page(name))]
    for n in nums:
        out.setdefault(str(n), {'page': BASE + name, 'title': title})
    if i % 25 == 0:
        print(i, name, title[:40], len(nums), flush=True)
json.dump(out, open(os.path.join(CACHE, 'paragraph-pages.json'), 'w'), indent=0)
missing = [n for n in range(1, 2866) if str(n) not in out]
print('paragraphs indexed:', len(out), 'missing:', len(missing), missing[:20])
