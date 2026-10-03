/*
 * Drives apps/anglican.html in a real browser against a LIVE appliance with realm-bible installed, and asserts what
 * a reader sees on fixed days whose answers are known from the 1979 Book of Common Prayer:
 *
 *   29 November 2026  the First Sunday of Advent — Year One begins; Isaiah 1:1-9 and 2 Peter 3:1-10 in the morning
 *   28 March 2027     Easter Day, a Principal Feast
 *   2 October 2026    Friday of Proper 21, Year Two — checked by hand against the lectionary (page 987): Psalm 102,
 *                     Hosea 10:1-15 and Luke 6:12-26 in the morning; Psalm 107:1-32 and Acts 21:37–22:16 at evening
 *   24 May 2027       Monday after Trinity Sunday, Proper 3, Year One (page 968): Psalm 25, Deuteronomy 4:9-14 and
 *                     2 Corinthians 1:1-11 in the morning; Psalms 9 and 15 and Luke 14:25-35 at evening
 *
 * Live rather than stubbed on purpose: the office is exactly what a stub would answer instantly and correctly
 * whatever the realm held.
 *
 *   APPLIANCE_URL=http://localhost:11043 APPLIANCE_USER=… APPLIANCE_PASSWORD=… node tests/anglican.live.mjs
 *
 * Screenshots land in SHOTS_DIR (default: the working directory). Needs `playwright` resolvable (npm i playwright).
 * Exits non-zero if any assertion failed.
 */
import { chromium } from 'playwright';

const base = process.env.APPLIANCE_URL ?? 'http://localhost:11043';
const url = `${base}/apps/realm-bible/anglican.html`;
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
  extraHTTPHeaders: { Authorization: authorization }, viewport: { width: 1280, height: 900 }, locale: 'en-US',
});
const page = await context.newPage();
const consoleErrors = [];
page.on('console', (m) => { if (m.type() === 'error' && !/favicon/.test(m.text())) consoleErrors.push(m.text()); });
page.on('pageerror', (e) => consoleErrors.push(String(e)));
const text = async (sel) => ((await page.locator(sel).first().textContent()) || '').replace(/\s+/g, ' ').trim();
const texts = async (sel) => (await page.locator(sel).allTextContents()).map((t) => t.replace(/\s+/g, ' ').trim());

/* A panel has settled when it shows content or its designed failure — never while it still says "…ing". */
async function settled(sel, timeout = 60000) {
  return page.waitForFunction((s) => {
    const el = document.querySelector(s);
    const t = el && el.textContent.trim();
    return t && t !== '…' && !/Reading|Searching|Opening|load when you scroll/.test(el.textContent);
  }, sel, { timeout }).then(() => true, () => false);
}
async function office(date, which) {
  await page.goto(`${url}?date=${date}&office=${which}`, { waitUntil: 'networkidle' });
  await page.locator('#day .dayname').waitFor({ timeout: 20000 });
  await page.waitForFunction(() => document.querySelectorAll('#lessons li').length > 0, null, { timeout: 20000 });
}

try {
  /* The First Sunday of Advent 2026, Morning Prayer. */
  await office('2026-11-29', 'morning');
  const badge = page.locator('#embabel-badge');
  const box = await badge.boundingBox();
  check('badge is visible in the viewport', (await badge.isVisible()) && box && box.y + box.height <= 900 + 1, box ? `y=${Math.round(box.y)}` : 'no box');
  check('badge links out', (await badge.locator('a').getAttribute('href')) === 'https://worlds.embabel.com');
  check('the badge is the shared one, verbatim', /Created with\s+Embabel Worlds/.test(await text('#embabel-badge')));

  check('29 November 2026 is the First Sunday of Advent', /First Sunday of Advent/.test(await text('#day .dayname')), await text('#day .dayname'));
  check('Advent is blue by custom, and the accent follows it', /Blue/.test(await text('#day .meta')) && /custom/.test(await text('#day .meta')) &&
    (await page.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue('--lit').trim())) === '#2f4f7f');
  check('the lectionary turns to Year One', /Year One/.test(await text('#day .meta')));
  check('morning psalms are 146 and 147', (await texts('#psalms .ref')).join(' | ') === 'Psalm 146 | Psalm 147', (await texts('#psalms .ref')).join(' | '));
  check('morning lessons are Isaiah 1:1-9 and 2 Peter 3:1-10', (await texts('#lessons li')).join(' | ') === 'Isaiah 1:1-9 | 2 Peter 3:1-10',
    (await texts('#lessons li')).join(' | '));
  check('the collect is the First Sunday of Advent\'s, in Rite Two', /First Sunday of Advent/.test(await text('#collect-name')) &&
    /^Almighty God, give us grace to cast away the works of darkness/.test(await text('#collect')));
  await page.locator('#r-1').click();
  check('Rite One gives the traditional collect', /^Almighty God, give us grace that we may cast away/.test(await text('#collect')) && /thy Son/.test(await text('#collect')));
  await page.locator('#r-2').click();
  check('Advent Sunday suggests the Third Song of Isaiah and the Song of Zechariah',
    /11\. The Third Song of Isaiah/.test(await text('#canticles')) && /16\. The Song of Zechariah/.test(await text('#canticles')), await text('#canticles'));
  await page.locator('#canticles [data-canticle="canticle-16"]').first().click();
  await page.locator('#canticles .canticle').first().waitFor({ timeout: 15000 }).then(() => true, () => false);
  check('a canticle opens with its text', /Blessed be the Lord, the God of Israel/.test(await text('#canticles .canticle')));

  /* A lesson opens in the reader with its verses shaded. */
  await page.locator('#lessons .ref').first().click();
  await page.locator('#reader [data-passage="Isaiah 1"]').waitFor({ timeout: 20000 });
  check('Isaiah 1:1-9 opens Isaiah 1 in the King James Version', /King James/.test(await text('#reader .sub')));
  check('its nine verses are shaded', (await page.locator('#reader p.match').count()) === 9, `${await page.locator('#reader p.match').count()}`);

  /* A psalm in the Prayer Book's own Psalter. */
  await page.locator('#psalms [data-psalter="146"]').click();
  await page.locator('#psalms .psalter').first().waitFor({ timeout: 15000 }).then(() => true, () => false);
  check('Psalm 146 shows in the 1979 Psalter, with its Latin incipit', /Lauda, anima mea/.test(await text('#psalms .psalter')) &&
    /Hallelujah! Praise the Lord, O my soul/.test(await text('#psalms .psalter')), (await text('#psalms .psalter')).slice(0, 80));

  /* Evening Prayer the same day: the Gospel is read at evening in Year One. */
  await page.locator('#o-evening').click();
  await page.waitForFunction(() => /Matthew 25/.test(document.querySelector('#lessons')?.textContent || ''), null, { timeout: 20000 }).then(() => true, () => false);
  check('the evening office is Psalms 111, 112, 113 and Matthew 25:1-13',
    (await texts('#psalms .ref')).join(', ') === 'Psalm 111, Psalm 112, Psalm 113' && (await texts('#lessons li')).join(' | ') === 'Matthew 25:1-13',
    `${(await texts('#psalms .ref')).join(', ')} / ${(await texts('#lessons li')).join(' | ')}`);
  check('Sunday evening suggests the Magnificat and the Nunc dimittis', /15\. The Song of Mary/.test(await text('#canticles')) && /17\. The Song of Simeon/.test(await text('#canticles')));

  /* Easter Day 2027. */
  await office('2027-03-28', 'morning');
  check('28 March 2027 is Easter Day', /Easter Day/.test(await text('#day .dayname')), await text('#day .dayname'));
  check('a Principal Feast, white', /Principal Feast/.test(await text('#day .dayname small')) && /White/.test(await text('#day .meta')));
  check('Easter morning: Psalms 148, 149, 150; Exodus 12:1-14 and John 1:1-18',
    (await texts('#psalms .ref')).join(', ') === 'Psalm 148, Psalm 149, Psalm 150' && (await texts('#lessons li')).join(' | ') === 'Exodus 12:1-14 | John 1:1-18',
    (await texts('#lessons li')).join(' | '));

  /* Two weekdays checked by hand against the Daily Office Lectionary. */
  await office('2026-10-02', 'morning');
  check('2 Oct 2026 is Friday of Proper 21, Year Two', /Proper 21/.test(await text('#day .dayname')) && /Year Two/.test(await text('#day .meta')));
  check('its morning: Psalm 102; Hosea 10:1-15 and Luke 6:12-26',
    (await texts('#psalms .ref')).join(', ') === 'Psalm 102' && (await texts('#lessons li')).join(' | ') === 'Hosea 10:1-15 | Luke 6:12-26',
    `${(await texts('#psalms .ref')).join(', ')} / ${(await texts('#lessons li')).join(' | ')}`);
  await office('2026-10-02', 'evening');
  check('its evening: Psalm 107:1-32; Acts 21:37–22:16',
    (await texts('#psalms .ref')).join(', ') === 'Psalm 107:1-32' && (await texts('#lessons li')).join(' | ') === 'Acts 21:37–22:16',
    `${(await texts('#psalms .ref')).join(', ')} / ${(await texts('#lessons li')).join(' | ')}`);
  await office('2027-05-24', 'morning');
  check('24 May 2027 is the Monday after Trinity Sunday, Proper 3, Year One',
    /Monday after Trinity Sunday \(Proper 3\)/.test(await text('#day .dayname')) && /Year One/.test(await text('#day .meta')), await text('#day .dayname'));
  check('its morning: Psalm 25; Deuteronomy 4:9-14 and 2 Corinthians 1:1-11',
    (await texts('#psalms .ref')).join(', ') === 'Psalm 25' && (await texts('#lessons li')).join(' | ') === 'Deuteronomy 4:9-14 | 2 Corinthians 1:1-11',
    `${(await texts('#psalms .ref')).join(', ')} / ${(await texts('#lessons li')).join(' | ')}`);
  await office('2027-05-24', 'evening');
  check('its evening: Psalms 9 and 15; Luke 14:25-35',
    (await texts('#psalms .ref')).join(', ') === 'Psalm 9, Psalm 15' && (await texts('#lessons li')).join(' | ') === 'Luke 14:25-35',
    `${(await texts('#psalms .ref')).join(', ')} / ${(await texts('#lessons li')).join(' | ')}`);
  check('and the Prayer Book calendar\'s commemoration, Jackson Kemper', /Jackson Kemper/.test(await text('#day')));

  /* A Holy Day, transferred: the Annunciation falls in Holy Week 2027 and is kept on the Monday after Easter 2. */
  await office('2027-04-05', 'morning');
  check('the Annunciation 2027 is transferred to 5 April', /Annunciation/.test(await text('#day .dayname')) && /transferred/.test(await text('#day')));

  /* The Articles of Religion: Article VI, its proofs opening in the reader. */
  await office('2026-11-29', 'morning');
  await page.locator('#articles').scrollIntoViewIfNeeded();
  await settled('#article-body');
  check('Article VI opens', /Sufficiency of the Holy Scriptures/.test(await text('#article-body')));
  check('with Scripture proofs', (await page.locator('#article-body .chips .ref').count()) > 0, `${await page.locator('#article-body .chips .ref').count()}`);
  await page.locator('#article-body .chips .ref').first().click();
  await page.waitForFunction(() => document.querySelectorAll('#reader p.match').length > 0, null, { timeout: 20000 }).then(() => true, () => false);
  check('a proof opens in the reader with its verses shaded', (await page.locator('#reader p.match').count()) > 0);
  await page.locator('#article-pick').selectOption('21');
  await page.waitForFunction(() => /General Councils/.test(document.querySelector('#article-body')?.textContent || ''), null, { timeout: 15000 }).then(() => true, () => false);
  check('Article XXI says it is omitted, and gives the 1571 text', /omitted/.test(await text('#article-body .text')) && /General Councils may not be gathered/.test(await text('#article-body .orig')));
  await page.locator('#aq').fill('predestination');
  await page.locator('#article-search button').click();
  await settled('#article-body');
  check('searching the Articles finds XVII', /XVII/.test(await text('#article-body')) && /Predestination/.test(await text('#article-body')));

  /* An Outline of the Faith, and the Church Catechism. */
  await page.locator('#outline').scrollIntoViewIfNeeded();
  await settled('#outline-body');
  check('the Outline opens at Human Nature', /What are we by nature\?/.test(await text('#outline-body')));
  const sections = await page.locator('#section-pick option').count();
  check('its sections are listed, with the 1662 Catechism', sections > 15 && /Church Catechism/.test(await text('#section-pick')), `${sections}`);
  await page.locator('#section-pick').selectOption('c:church-catechism');
  await page.waitForFunction(() => /What is your Name\?/.test(document.querySelector('#outline-body')?.textContent || ''), null, { timeout: 15000 }).then(() => true, () => false);
  check('the Church Catechism opens with "What is your Name?"', /What is your Name\?/.test(await text('#outline-body')));
  await page.locator('#cq').fill('grace');
  await page.locator('#catechism-search button').click();
  await settled('#outline-body');
  check('searching the catechisms for "grace" answers from both', (await page.locator('#outline-body .qa').count()) > 1 &&
    /Outline of the Faith/.test(await text('#outline-body')) && /Church Catechism/.test(await text('#outline-body')));

  /* The canticles, all twenty-one. */
  await page.locator('#all-canticles').scrollIntoViewIfNeeded();
  await settled('#canticles-body');
  check('all twenty-one canticles are listed', (await page.locator('#canticles-body details').count()) === 21);

  /* Prayers and Thanksgivings. */
  await page.locator('#open-prayers').click();
  await page.locator('#prayers-body .prayer').first().waitFor({ timeout: 20000 }).then(() => true, () => false);
  check('the Prayers and Thanksgivings open, all 81', (await page.locator('#prayers-body .prayer').count()) === 81, `${await page.locator('#prayers-body .prayer').count()}`);
  await page.locator('#pq').fill('peace');
  await page.locator('#prayer-search button').click();
  await page.waitForFunction(() => /For Peace/.test(document.querySelector('#prayers-body')?.textContent || ''), null, { timeout: 15000 }).then(() => true, () => false);
  check('finding "peace" narrows them', /For Peace/.test(await text('#prayers-body')) && (await page.locator('#prayers-body .prayer').count()) < 81,
    `${await page.locator('#prayers-body .prayer').count()}`);
  await page.locator('#close-prayers').click();

  /* A day outside the stored calendar says so. */
  await page.goto(`${url}?date=2031-06-01`, { waitUntil: 'networkidle' });
  await settled('#day');
  check('a day outside the calendar says so', /outside the stored calendar/.test(await text('#day')));

  /* How it works. */
  await page.getByRole('link', { name: 'How it works' }).click();
  check('How it works opens', await page.locator('#how-it-works').isVisible());
  check('How it works shows the query', /DailyOffice/.test(await text('#how-it-works')) && /OfficeDay/.test(await text('#how-it-works pre')));

  /* Screenshots, desktop and phone, of the front page on the First Sunday of Advent. */
  await office('2026-11-29', 'morning');
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${shots}/anglican-desktop.png`, fullPage: true });
  const phone = await browser.newContext({ extraHTTPHeaders: { Authorization: authorization }, viewport: { width: 390, height: 844 }, locale: 'en-US' });
  const p2 = await phone.newPage();
  p2.on('pageerror', (e) => consoleErrors.push(String(e)));
  await p2.goto(`${url}?date=2026-11-29&office=morning`, { waitUntil: 'networkidle' });
  await p2.waitForTimeout(4000);
  const overflow = await p2.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  check('no horizontal scroll at phone width', overflow <= 1, `${overflow}px`);
  await p2.screenshot({ path: `${shots}/anglican-phone.png`, fullPage: true });
  await phone.close();

  check('no console errors', consoleErrors.length === 0, consoleErrors.slice(0, 3).join(' | '));
} catch (e) {
  check('the page could be driven', false, String(e));
} finally {
  await browser.close();
}
console.log(failures ? `\n${failures} failed` : '\nall passed');
process.exit(failures ? 1 : 0);
