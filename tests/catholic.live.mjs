/*
 * Drives apps/catholic.html in a real browser against a LIVE appliance with realm-bible installed, and asserts
 * what a reader sees on fixed days whose answers are known: 1 October 2026 (St Thérèse, a memorial, white,
 * a Thursday — the Luminous Mysteries), 1 November 2026 (All Saints, a holy day of obligation).
 *
 * Live rather than stubbed on purpose: the calendar, the saints' cards and the catechism are exactly what a stub
 * would answer instantly and correctly whatever the realm held.
 *
 *   APPLIANCE_URL=http://localhost:11043 APPLIANCE_USER=… APPLIANCE_PASSWORD=… node tests/catholic.live.mjs
 *
 * Panels fed by public services (Wikidata, Wikipedia, OpenStreetMap) may be slow or unreachable; the test
 * accepts their designed "could not be fetched" state as long as it says so and offers a retry — what it never
 * accepts is a blank panel or an endless spinner. Screenshots land in SHOTS_DIR (default: the working directory).
 *
 * Needs `playwright` resolvable (npm i playwright). Exits non-zero if any assertion failed.
 */
import { chromium } from 'playwright';

const base = process.env.APPLIANCE_URL ?? 'http://localhost:11043';
const url = `${base}/apps/realm-bible/catholic.html`;
const shots = process.env.SHOTS_DIR ?? '.';
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
/* Sent up front: the appliance redirects an unauthenticated page to its login rather than answering 401. */
const authorization = 'Basic ' + Buffer.from(`${credentials.username}:${credentials.password}`).toString('base64');
const context = await browser.newContext({
  extraHTTPHeaders: { Authorization: authorization }, viewport: { width: 1280, height: 900 }, locale: 'en-IE',
});
const page = await context.newPage();
const consoleErrors = [];
page.on('console', (m) => { if (m.type() === 'error' && !/tile\.openstreetmap|favicon/.test(m.text())) consoleErrors.push(m.text()); });
page.on('pageerror', (e) => consoleErrors.push(String(e)));
const text = (sel) => page.locator(sel).first().textContent();

/* A panel has settled when it shows content or its designed failure — never while it still says "…ing". */
async function settled(sel, timeout = 60000) {
  return page.waitForFunction((s) => {
    const el = document.querySelector(s);
    const t = el && el.textContent.trim();
    return t && t !== '…' && !/Reading|Asking|Finding|Fetching|Searching|Opening|Looking up|load when you scroll/.test(el.textContent);
  }, sel, { timeout }).then(() => true, () => false);
}

try {
  await page.goto(`${url}?date=2026-10-01`, { waitUntil: 'networkidle' });

  const badge = page.locator('#embabel-badge');
  const box = await badge.boundingBox();
  check('badge is visible in the viewport', (await badge.isVisible()) && box && box.y + box.height <= 900 + 1, box ? `y=${Math.round(box.y)}` : 'no box');
  check('badge links out', (await badge.locator('a').getAttribute('href')) === 'https://worlds.embabel.com');
  check('manifest preflight passes', !(await page.locator('#feast .problem').count()));

  /* Today: 1 October 2026 is St Thérèse, a memorial, white, on a Thursday. */
  await page.locator('#feast .feast').waitFor({ timeout: 20000 });
  check('the feast is St Thérèse', /Thérèse/.test(await text('#feast .feast')), (await text('#feast .feast')).trim().slice(0, 60));
  check('its rank is shown as a memorial', /Memorial/.test(await text('#feast .feast small')));
  check('the colour is white, and the accent follows it',
    /White/.test(await text('#feast .meta')) &&
    (await page.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue('--lit').trim())) === '#a67c2e');
  check('no obligation notice on an ordinary memorial', (await page.locator('#feast .obligation').count()) === 0);

  /* The saint: a card with her name, or the designed failure naming the source and offering a retry. */
  await settled('#saint-body', 90000);
  const saintText = await text('#saint-body');
  const saintOk = /Thérèse/.test(saintText) && ((await page.locator('#saint-body .life').count()) > 0 || (await page.locator('#saint-body .facts').count()) > 0);
  const saintDesigned = (await page.locator('#saint-body .problem').count()) > 0 && (await page.locator('#saint-body [data-retry]').count()) > 0;
  check('the saint of the day renders her card, or says why not and offers a retry', saintOk || saintDesigned,
    saintOk ? 'card' : saintDesigned ? 'designed failure: ' + saintText.trim().slice(0, 120) : saintText.trim().slice(0, 120));
  if (saintOk) {
    const mapOk = await page.locator('#map.leaflet-container').waitFor({ timeout: 20000 }).then(() => true, () => false);
    check('her places are mapped', mapOk);
    check('places are listed with their kind', (await page.locator('#saint-body .places li').count()) > 0);
    check('no empty "also honoured" line on a one-saint day', !/Also honoured today:\s*$/m.test(await text('#saint-body')) &&
      !(await page.locator('#saint-body .also').count()));
    const desc = await text('#saint-body .desc');
    check('her dates are shown once', (desc.match(/1873/g) || []).length === 1, desc.trim());
    const facts = await text('#saint-body .facts');
    check('her feast is the calendar\'s 1 October, Wikidata\'s 3 October only as "also kept on"',
      /1 October|October 1/.test(facts) && !/Feast\s*October 3/.test(facts) && /also kept on October 3/.test(facts), facts.replace(/\s+/g, ' ').trim().slice(0, 200));
  }

  /* The Rosary: Thursday → the Luminous Mysteries, five of them, each opening its Scripture. */
  await settled('#rosary-body');
  check('Thursday prays the Luminous Mysteries', /Luminous/.test(await text('#rosary-lede')));
  check('five mysteries are listed', (await page.locator('#rosary-body ol.mysteries li').count()) === 5);
  await page.locator('#rosary-body .ref').first().click();
  await page.locator('#reader [data-passage="Matthew 3"]').waitFor({ timeout: 20000 });
  check('the first mystery opens Matthew 3 in the reader', true);
  check('its verses (13–17) are shaded', (await page.locator('#reader p.match').count()) === 5, `${await page.locator('#reader p.match').count()}`);

  /* The catechism: a saint's day asks about the communion of saints; the CCC links go to vatican.va. */
  await settled('#catechism-today');
  check('the catechism panel picks a topic from the day', /saints/i.test(await text('#catechism-lede')));
  check('CCC paragraphs link to the Vatican', (await page.locator('#catechism-today .ccc a[href^="https://www.vatican.va/"]').count()) > 0);
  check('public-domain answers are shown', (await page.locator('#catechism-today .qa').count()) > 0);
  await page.locator('#cq').fill('grace');
  await page.locator('#catechism-search button').click();
  await settled('#catechism-results');
  check('searching the catechism for "grace" answers', (await page.locator('#catechism-results .qa').count()) > 0);
  await page.locator('#lesson').selectOption('1');
  await page.waitForFunction(() => /Lesson 1/.test(document.querySelector('#catechism-results')?.textContent || ''), null, { timeout: 15000 })
    .then(() => true, () => false);
  check('Baltimore lesson 1 opens with "Who made the world?"', /Who made the world\?/.test(await text('#catechism-results')));

  /* Saints in Scripture: loads when scrolled into view; a chapter opens in the reader. */
  await page.locator('#scripture-saints').scrollIntoViewIfNeeded();
  await settled('#scripture-saints-body');
  check('saints in Scripture are listed', (await page.locator('#scripture-saints-body li').count()) > 10,
    `${await page.locator('#scripture-saints-body li').count()}`);
  check('Peter and Paul are among them', /Peter/.test(await text('#scripture-saints-body')) && /Paul/.test(await text('#scripture-saints-body')));
  await page.locator('#scripture-saints-body [data-passage]').first().click();
  await page.locator('#reader [data-passage]').waitFor({ timeout: 20000 });
  check('a saint\'s chapter opens in the reader', (await page.locator('#reader .chapter p').count()) > 3);

  /* Saints of the reader's country, from the locale (en-IE → Ireland). */
  await page.locator('#country').scrollIntoViewIfNeeded();
  check('the country comes from the locale', /Ireland/.test(await text('#country-name')));
  await settled('#country-body', 120000);
  const countryOk = (await page.locator('#country-body li').count()) > 0;
  const countryDesigned = (await page.locator('#country-body .problem').count()) > 0 && (await page.locator('#country-body [data-retry]').count()) > 0;
  check('Irish saints are listed, or the panel says Wikidata could not be reached and offers a retry', countryOk || countryDesigned,
    countryOk ? `${await page.locator('#country-body li').count()} listed` : (await text('#country-body')).trim().slice(0, 120));

  /* Prayers. */
  await page.locator('#open-prayers').click();
  await page.locator('#prayers-body .prayer').first().waitFor({ timeout: 20000 }).then(() => true, () => false);
  check('the prayers open, the Our Father among them', /Our Father/.test(await text('#prayers-body')) && /Hail Mary/.test(await text('#prayers-body')));
  await page.locator('#close-prayers').click();

  /* A holy day of obligation: All Saints, 1 November 2026. */
  await page.locator('#pick-day').fill('2026-11-01');
  await page.locator('#pick-day').dispatchEvent('change');
  await page.waitForFunction(() => /All Saints/.test(document.querySelector('#feast .feast')?.textContent || ''), null, { timeout: 20000 })
    .then(() => true, () => false);
  check('1 November is All Saints, a solemnity', /All Saints/.test(await text('#feast .feast')) && /Solemnity/.test(await text('#feast .feast small')));
  check('and a holy day of obligation', (await page.locator('#feast .obligation').count()) === 1);
  await page.locator('#prev-day').click();
  await page.waitForFunction(() => /31 October|October 31/.test(document.querySelector('#datestr')?.textContent || ''), null, { timeout: 15000 })
    .then(() => true, () => false);
  check('the arrows move a day', /31/.test(await text('#datestr')));

  /* A day outside the stored calendar says so. */
  await page.goto(`${url}?date=2031-06-01`, { waitUntil: 'networkidle' });
  await settled('#feast');
  check('a day outside the calendar says so', /outside the stored calendar/.test(await text('#feast')));

  /* Search still works in the Catholic edition (the shared core). */
  await page.goto(`${url}?date=2026-10-01&q=${encodeURIComponent('the angel Gabriel greets a young woman and tells her she will bear a son')}`, { waitUntil: 'networkidle' });
  await page.locator('#results .card').first().waitFor({ timeout: 60000 }).then(() => true, () => false);
  check('the shared search finds Luke 1 for the Annunciation', /Luke 1/.test((await page.locator('#results .card .passage').allTextContents()).join(' ')));

  /* How it works. */
  await page.getByRole('link', { name: 'How it works' }).click();
  check('How it works opens', await page.locator('#how-it-works').isVisible());
  check('How it works shows the queries', /TodayInTheChurch/.test(await text('#how-it-works')) && /LiturgicalDay/.test(await text('#how-it-works pre')));

  /* Screenshots, desktop and phone, of the front page on St Thérèse's day. */
  await page.goto(`${url}?date=2026-10-01`, { waitUntil: 'networkidle' });
  await settled('#saint-body', 90000);
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${shots}/catholic-desktop.png`, fullPage: true });
  const phone = await browser.newContext({ extraHTTPHeaders: { Authorization: authorization }, viewport: { width: 390, height: 844 }, locale: 'en-IE' });
  const p2 = await phone.newPage();
  await p2.goto(`${url}?date=2026-10-01`, { waitUntil: 'networkidle' });
  await p2.waitForTimeout(4000);
  const overflow = await p2.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  check('no horizontal scroll at phone width', overflow <= 1, `${overflow}px`);
  await p2.screenshot({ path: `${shots}/catholic-phone.png`, fullPage: true });
  await phone.close();

  check('no console errors', consoleErrors.length === 0, consoleErrors.slice(0, 3).join(' | '));
} catch (e) {
  check('the page could be driven', false, String(e));
} finally {
  await browser.close();
}
console.log(failures ? `\n${failures} failed` : '\nall passed');
process.exit(failures ? 1 : 0);
