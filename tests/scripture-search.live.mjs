/*
 * Drives apps/scripture-search.html in a real browser against a LIVE appliance with realm-bible
 * installed and its `bible-web` documents ingested, and asserts what a reader sees.
 *
 * Live rather than stubbed on purpose: what this app depends on — a search by meaning and a join to a
 * published CSV — is exactly what a stub would answer instantly and correctly, whatever the engine did.
 *
 *   APPLIANCE_URL=http://localhost:11043 APPLIANCE_USER=… APPLIANCE_PASSWORD=… node tests/scripture-search.live.mjs
 *
 * Needs `playwright` resolvable (npm i playwright). Exits non-zero on the first failed assertion.
 */
import { chromium } from 'playwright';

const base = process.env.APPLIANCE_URL ?? 'http://localhost:11043';
const url = `${base}/apps/realm-bible/scripture-search.html`;
const credentials = { username: process.env.APPLIANCE_USER, password: process.env.APPLIANCE_PASSWORD };
if (!credentials.username || !credentials.password) {
  console.error('Set APPLIANCE_USER and APPLIANCE_PASSWORD.');
  process.exit(2);
}

let failures = 0;
function check(what, ok, detail = '') {
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${what}${detail ? ` — ${detail}` : ''}`);
  if (!ok) failures++;
}

const browser = await chromium.launch();
/* Sent up front: the appliance redirects an unauthenticated page to its login rather than answering 401,
   so credentials offered only on a challenge are never offered at all. */
const authorization = 'Basic ' + Buffer.from(`${credentials.username}:${credentials.password}`).toString('base64');
const context = await browser.newContext({ extraHTTPHeaders: { Authorization: authorization }, viewport: { width: 1280, height: 860 } });
const page = await context.newPage();
const consoleErrors = [];
page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text()); });
page.on('pageerror', (e) => consoleErrors.push(String(e)));

const firstCard = () => page.locator('.card').first();
const readerTitle = () => page.locator('#reader [data-passage]').getAttribute('data-passage');

try {
  await page.goto(url, { waitUntil: 'networkidle' });

  /* The badge a reader sees: present, non-empty, linking out, inside the viewport. */
  const badge = page.locator('#embabel-badge');
  const box = await badge.boundingBox();
  check('badge is visible in the viewport', (await badge.isVisible()) && box && box.y + box.height <= 860 + 1,
    box ? `y=${Math.round(box.y)}` : 'no box');
  check('badge links out', (await badge.locator('a').getAttribute('href')) === 'https://worlds.embabel.com');
  check('manifest preflight passes (no unavailable-capability state)', !(await page.locator('.problem').count()));

  /* The front page's question, from an example. */
  const t0 = Date.now();
  await page.getByRole('button', { name: 'the tent peg' }).click();
  await firstCard().waitFor({ timeout: 30000 });
  const searchMs = Date.now() - t0;
  /* Budget 10 s, not 2: the search is an agentic loop (4–8 s measured) and the page states the wait up front. */
  check('search answers inside the 10 s agentic budget', searchMs < 10000, `${searchMs} ms`);
  /* Either telling is right: Judges 4 narrates Jael and the tent peg, Judges 5 sings it. The agentic loop
     keeps only chapters it judges to fit, and on a given run may keep one, the other, or both — so the
     reader checks below follow whichever chapter opened. */
  const tellings = { 'Judges 4': { peg: '21', jael: 4 }, 'Judges 5': { peg: '26', jael: 2 } };
  const first = await firstCard().locator('.passage').textContent();
  const telling = tellings[first];
  check('closest chapter for the tent peg is Judges 4 or 5', !!telling, first);
  check('at least one chapter comes back', (await page.locator('.card').count()) >= 1, `${await page.locator('.card').count()}`);
  await page.locator('#reader [data-passage]').waitFor();
  check('the reader opens the closest chapter', (await readerTitle()) === first);
  check('the matched verses are highlighted', (await page.locator('#reader p.match').count()) > 0,
    `${await page.locator('#reader p.match').count()} verses`);

  /* KJV by default, WEB on the toggle — from the same rows, no new call. */
  const peg = () => page.locator(`#reader p[data-n="${telling.peg}"]`);
  check('KJV by default', /nail/.test(await peg().textContent()));
  await page.locator('#t-web').click();
  check('WEB on the toggle', /tent peg/.test(await peg().textContent()));
  await page.locator('#t-kjv').click();

  /* People, joined from Theographic when the chapter opens. */
  const jael = page.locator('.person-chip', { hasText: 'Jael' });
  await jael.waitFor({ timeout: 15000 });
  check(`people in ${first} include Jael`, await jael.isVisible());
  await jael.click();
  const jaelVerses = await page.locator('#reader p.person').count();
  check(`Jael highlights her ${telling.jael} verses`, jaelVerses === telling.jael, `${jaelVerses}`);

  /* One verse in seven translations; an Old Testament verse has six, and the YLT gap is not an error. */
  await peg().click();
  await page.locator('#compare .tr').first().waitFor({ timeout: 20000 });
  const translations = await page.locator('#compare .tr').count();
  check(`${first}:${telling.peg} in six translations (no YLT for the Old Testament)`, translations === 6, `${translations}`);
  check('the expected YLT gap is explained, not reported as a failure',
    (await page.locator('#compare .problem').count()) === 0 && /New Testament only/.test(await page.locator('#compare').textContent()));
  check('and the page-wide state bar does not announce it either',
    !/Partial result/.test(await page.locator('#state').evaluate((el) => (el.shadowRoot ? el.shadowRoot.textContent : el.textContent) || '')));

  /* A search superseded by the next one must not paint over it. */
  await page.locator('#q').fill('a younger brother is sold by jealous siblings who lie to their father');
  await page.locator('#q').press('Enter');
  await page.locator('#q').fill('love is patient and kind and does not keep a record of wrongs');
  await page.locator('#q').press('Enter');
  await page.waitForFunction(() => document.querySelector('.card .passage')?.textContent === '1 Corinthians 13', null, { timeout: 30000 })
    .then(() => check('the later search wins', true), () => check('the later search wins', false, 'first card never became 1 Corinthians 13'));
  await page.waitForTimeout(1500);
  check('the earlier search does not repaint afterwards',
    (await firstCard().locator('.passage').textContent()) === '1 Corinthians 13');

  /* The question that exposed the single-pass search: a story told in words the chapter does not use. */
  await page.locator('#q').fill('bears eat boys who mocked a prophet');
  await page.locator('#q').press('Enter');
  await page.waitForFunction(() => document.querySelector('.card .passage')?.textContent === '2 Kings 2', null, { timeout: 30000 })
    .then(() => check('"bears eat boys who mocked a prophet" finds 2 Kings 2', true), () => check('"bears eat boys who mocked a prophet" finds 2 Kings 2', false));
  check('the KJV prints the divine name in small capitals', (await page.locator('#reader .sc').count()) > 0);
  check('the chapter opens with an illuminated initial', (await page.locator('#reader p.first').count()) === 1);

  /* A deep link answers on load. */
  await page.goto(`${url}?q=${encodeURIComponent('the shepherd boy David fights the Philistine champion Goliath')}`, { waitUntil: 'networkidle' });
  await firstCard().waitFor({ timeout: 30000 });
  check('a ?q= link answers on load (1 Samuel 17)', (await firstCard().locator('.passage').textContent()) === '1 Samuel 17');

  /* How it works: discreet, and there. */
  await page.getByRole('link', { name: 'How it works' }).click();
  check('How it works opens', await page.locator('#how-it-works').isVisible());
  check('How it works shows the Cypher the app runs', /RELEVANT_TO/.test(await page.locator('#how-it-works pre').first().textContent()));

  check('no console errors', consoleErrors.length === 0, consoleErrors.slice(0, 3).join(' | '));
} catch (e) {
  check('the page could be driven', false, String(e));
} finally {
  await browser.close();
}
console.log(failures ? `\n${failures} failed` : '\nall passed');
process.exit(failures ? 1 : 0);
