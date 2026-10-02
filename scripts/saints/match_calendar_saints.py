"""Search Wikidata for each canonized calendar saint and keep the first human with a canonization status or feast day."""
import json, time, urllib.parse, urllib.request
UA = {'User-Agent': 'realm-bible-build/0.1 (https://github.com/embabel-worlds/realm-bible)'}
TITLES = {'bishop','priest','martyr','martyrs','pope','virgin','abbot','abbess','religious','deacon','doctor','monk','hermit','layman','laywoman','companions','apostle','evangelist','king','queen','widow','missionary','founder','presbyter','the','and'}
def get(url):
    for i in range(4):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60))
        except Exception as e:
            time.sleep(2 + 3*i)
    raise RuntimeError(url)
def search_terms(mid):
    words = mid.split('_')
    while words and words[-1] in TITLES: words.pop()
    return ' '.join(words)
mart = json.load(open('../romcal-probe/martyrology.json'))
people = [m for m in mart if m.get('canon')]
out = []
for m in people:
    term = search_terms(m['id'])
    ids = []
    for q in (term, ('Saint ' if m['canon']=='SAINT' else 'Blessed ') + term, ' '.join(term.split()[:2])):
        res = get('https://www.wikidata.org/w/api.php?' + urllib.parse.urlencode({'action':'wbsearchentities','search':q,'language':'en','limit':'10','format':'json'}))
        ids += [s['id'] for s in res.get('search', []) if s['id'] not in ids]
    pick = None; cands = []
    if ids:
        q = 'SELECT ?wd ?wdLabel ?wdDescription (SAMPLE(?h) AS ?human) (SAMPLE(?c) AS ?canon) (SAMPLE(?f) AS ?feast) WHERE { VALUES ?wd { %s } OPTIONAL { VALUES ?ht { wd:Q5 wd:Q20643955 } ?wd wdt:P31 ?ht BIND(1 AS ?h) } OPTIONAL { ?wd wdt:P411 ?c } OPTIONAL { ?wd wdt:P841 ?f } SERVICE wikibase:label { bd:serviceParam wikibase:language "en". } } GROUP BY ?wd ?wdLabel ?wdDescription' % ' '.join('wd:'+i for i in ids)
        rows = get('https://query.wikidata.org/sparql?' + urllib.parse.urlencode({'query': q, 'format': 'json'}))['results']['bindings']
        info = {r['wd']['value'].rsplit('/',1)[1]: {k: v['value'] for k, v in r.items()} for r in rows}
        for i in ids:
            r = info.get(i, {})
            cands.append({'qid': i, 'label': r.get('wdLabel'), 'desc': r.get('wdDescription'), 'human': 'human' in r, 'canon': 'canon' in r, 'feast': 'feast' in r})
        # Prefer an item with BOTH a canonization status and a feast day, then either.
        for need in (lambda c: c['human'] and c['canon'] and c['feast'], lambda c: c['human'] and (c['canon'] or c['feast'])):
            pick = next((c['qid'] for c in cands if need(c)), None)
            if pick: break
    out.append({'id': m['id'], 'term': term, 'celebrationName': m['celebrationName'], 'date': m['date'], 'canon': m['canon'], 'pick': pick, 'candidates': cands[:4]})
    time.sleep(0.3)
json.dump(out, open('matches.json', 'w'), indent=1, ensure_ascii=False)
print(len(out), 'saints;', sum(1 for o in out if o['pick']), 'picked')
