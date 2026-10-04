/*
 * Runs EVERY view this realm ships against a LIVE appliance, and fails on any that the engine refuses.
 *
 * Why it exists: `PassagesMentioning` shipped with Cypher the database refuses on every call (it ordered by
 * variables an aggregating RETURN had already dropped). The realm validated clean and loaded with no
 * problems, because loading checks a view's shape, not whether its query runs — and the agent batteries
 * routed around it. It was found by a person asking an agent about the Philistines. A view that has never
 * returned rows in front of you does not exist yet.
 *
 * Two passes:
 *   - every view by name, with its declared defaults — so a view added later is covered without anyone
 *     remembering to add it here;
 *   - the cases below: varied parameters, with what the answer must contain, so a view that "succeeds"
 *     with the wrong rows fails too.
 * A view is read from `views/*.yml` by its `- name:` line; no YAML library is needed for that.
 *
 *   APPLIANCE_URL=http://localhost:11043 APPLIANCE_USER=… APPLIANCE_PASSWORD=… node tests/views.smoke.mjs [--with-llm]
 *
 * Views that call a model or the news (SearchPassages, TodaysHeadlines, PassagesForStory) cost money and
 * vary run to run, so they run only with --with-llm. Views fed by public services (Wikidata, getbible,
 * bible-api) can be slow on a cold cache; durations are printed, and anything over SLOW_MS is flagged.
 * Exits non-zero if any check failed.
 */
import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

const base = process.env.APPLIANCE_URL ?? 'http://localhost:11043';
const user = process.env.APPLIANCE_USER;
const password = process.env.APPLIANCE_PASSWORD;
if (!user || !password) {
  console.error('Set APPLIANCE_USER and APPLIANCE_PASSWORD.');
  process.exit(2);
}
const withLlm = process.argv.includes('--with-llm');
const SLOW_MS = Number(process.env.SLOW_MS ?? 5000);
const LLM_VIEWS = new Set(['SearchPassages', 'TodaysHeadlines', 'PassagesForStory']);

/* A default that is deliberately empty (no reference, no book) answers nothing; that is the designed
 * result, not a defect. Today-dependent views may also be empty on a day with nothing to keep. */
const EMPTY_BY_DEFAULT = new Set(['ReadVerseDouayRheims', 'ReadDeuterocanon', 'SaintsOfTheDay']);

/* [view, params, a pattern the rows must contain (or null for "some rows")] */
const CASES = [
  ['ReadVerse', { ref: 'Ruth 1:16', translation: 'web' }, /where you go/i],
  ['ReadPassage', { passage: 'Psalms 23', translation: 'kjv' }, /shepherd/i],
  ['SearchVerses', { term: 'Philistines', limit: 5 }, /Philistines/],
  ['PassagesMentioning', { term: 'Philistines' }, /Samuel/],
  ['PassagesMentioning', { term: 'Philistines', translation: 'web' }, /Samuel/],
  ['CompareTranslations', { ref: 'John 1:1' }, /Word/],
  ['ReadVerseDouayRheims', { ref: 'Psalms 23:1' }, /ruleth me/],
  ['PeopleNamed', { name: 'Zechariah' }, /Zechariah/],
  ['VersesAboutPerson', { name: 'Ruth', translation: 'web' }, /Ruth/],
  ['PeopleInPassage', { passage: 'Genesis 22' }, /Abraham/],
  ['Parents', { name: 'David' }, /Jesse/],
  ['TribeOf', { name: 'David' }, /Judah/],
  ['GenerationFromAdam', { name: 'Moses' }, null],
  ['TribalChapters', { tribe: 'Judah' }, null],
  ['TodayInTheChurch', { date: '2026-11-01' }, /All Saints/],
  ['FeastsInRange', { from: '2026-12-01', to: '2026-12-31' }, /Christmas|Nativity/i],
  ['RosaryToday', { date: '2026-10-01' }, /luminous/i],
  ['Prayers', { name: 'Hail Holy Queen' }, /banished children of Eve/],
  ['CatechismLesson', { catechism: 'baltimore-2', lesson: 1 }, /God/],
  ['CatechismSearch', { term: 'grace', catechism: 'baltimore-2' }, /grace/i],
  ['CatechismOnTopic', { topic: 'purgatory', catechism: 'baltimore-2' }, /venial/],
  ['CatechismOnTopic', { topic: 'Mass Sunday', catechism: 'baltimore-2' }, /holydays? of obligation/i],
  ['ReadDeuterocanon', { book: 'Sirach', chapter: 6, verse: 14 }, /strong defence/],
  ['ReadDeuterocanonPassage', { book: 'Tobit', chapter: 12 }, /Raphael/],
  ['SearchDeuterocanon', { term: 'Susanna' }, /Susanna/],
  ['SaintsOfTheDay', { date: '2026-10-01' }, /Th[ée]r[èe]se/],
  ['FindSaint', { name: 'Therese' }, /Lisieux/],
  ['SaintLife', { wd: 'Q181715' }, /Alen[cç]on/],
  ['SaintsOfCountry', { country: 'Ireland', limit: 10 }, /Columba|Patrick|Brigid/],
  ['SaintsOfCountry', { country: 'PL', limit: 10 }, /Kolbe|Faustina|John Paul/],
  ['SaintsInScripture', {}, /Peter|Paul/],
];

const auth = 'Basic ' + Buffer.from(`${user}:${password}`).toString('base64');
async function invoke(name, args) {
  const started = Date.now();
  const res = await fetch(`${base}/api/v1/views/${encodeURIComponent(name)}/invoke`, {
    method: 'POST',
    headers: { Authorization: auth, 'Content-Type': 'application/json' },
    body: JSON.stringify({ args }),
  });
  const body = await res.json().catch(() => ({}));
  return { http: res.status, ms: Date.now() - started, body };
}

const viewsDir = new URL('../views/', import.meta.url).pathname;
const names = readdirSync(viewsDir).filter(f => f.endsWith('.yml')).sort()
  .flatMap(f => [...readFileSync(join(viewsDir, f), 'utf8').matchAll(/^- name:\s*(\S+)/gm)].map(m => m[1]));

let failures = 0;
const report = (ok, line) => { if (!ok) failures++; console.log(`${ok ? 'PASS' : 'FAIL'}  ${line}`); };

console.log(`== every view, with its defaults (${names.length})`);
for (const name of names) {
  if (LLM_VIEWS.has(name) && !withLlm) { console.log(`SKIP  ${name} (model or news; --with-llm)`); continue; }
  const { http, ms, body } = await invoke(name, {});
  const rows = body.data?.length ?? 0;
  const problem = http !== 200 || body.status !== 'SUCCEEDED'
    ? `${http} ${body.status ?? ''} ${body.error?.message?.slice(0, 160) ?? ''}`
    : rows === 0 && !EMPTY_BY_DEFAULT.has(name) ? 'no rows with its defaults' : null;
  report(!problem, `${name.padEnd(26)} ${String(rows).padStart(4)} rows ${String(ms).padStart(6)}ms${ms > SLOW_MS ? ' SLOW' : ''}${problem ? '  ' + problem : ''}`);
}

console.log(`\n== cases (${CASES.length})`);
const known = new Set(names);
for (const [name, args, pattern] of CASES) {
  if (!known.has(name)) { report(false, `${name} is not a view in this realm any more`); continue; }
  const { http, ms, body } = await invoke(name, args);
  const rows = body.data ?? [];
  const text = JSON.stringify(rows);
  const problem = http !== 200 || body.status !== 'SUCCEEDED'
    ? `${http} ${body.status ?? ''} ${body.error?.message?.slice(0, 160) ?? ''}`
    : rows.length === 0 ? 'no rows'
    : pattern && !pattern.test(text) ? `rows lack ${pattern}` : null;
  report(!problem, `${name.padEnd(26)} ${JSON.stringify(args).slice(0, 60).padEnd(60)} ${String(ms).padStart(6)}ms${ms > SLOW_MS ? ' SLOW' : ''}${problem ? '  ' + problem : ''}`);
}

console.log(failures ? `\n${failures} check(s) failed` : '\nall passed');
process.exit(failures ? 1 : 0);
