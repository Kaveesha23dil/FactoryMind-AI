/* Read-only overview acceptance test. API fixtures are fetched from actual saved data. */
import assert from 'node:assert/strict';
import { pathToFileURL } from 'node:url';
import { mkdir } from 'node:fs/promises';
const modulePath = process.env.PLAYWRIGHT_MODULE;
const { chromium } = await import(modulePath ? pathToFileURL(`${modulePath}/index.mjs`).href : 'playwright');
const web = process.env.SETTINGS_WEB_URL || 'http://localhost:3000';
const api = process.env.SETTINGS_API_URL || 'http://127.0.0.1:8000';
const browser = await chromium.launch({ channel: 'msedge', headless: true });
try {
 const response = await fetch(`${api}/api/submission/overview`);
 assert.equal(response.status, 200);
 const actual = await response.json();
 let overview = actual; let offline = false; let reads = 0;
 const page = await browser.newPage({ viewport: { width: 1440, height: 1050 }, reducedMotion: 'reduce' });
 const errors = []; const methods = [];
 page.on('pageerror', error => errors.push(error.message));
 async function serve(route) {
  const method = route.request().method(); methods.push(method); assert.equal(method, 'GET');
  const incoming = new URL(route.request().url());
  const path = incoming.pathname.replace(/^\/api\/backend/, '');
  if (path === '/api/submission/overview') reads++;
  if (offline) return route.fulfill({ status: 503, json: { detail: 'Unavailable' } });
  if (path === '/api/submission/overview') return route.fulfill({ json: overview });
  const result = await fetch(`${api}${path}${incoming.search}`);
  await route.fulfill({ status: result.status, body: await result.text(), contentType: 'application/json' });
 }
 await page.route('**/api/**', serve); await page.route('**/health', serve);
 await page.goto(`${web}/overview`);
 await page.getByText('API connected', { exact: true }).waitFor();
 await page.getByRole('heading', { name: 'From Machine Anomalies to Explainable Decisions.', exact: true }).waitFor();
 assert.equal(await page.locator('.fm-eyebrow,.fm-breadcrumb,.fm-metric-art,.fm-integrity,.fm-dataset').count(), 0);
 const links = await page.getByRole('complementary', { name: 'Primary navigation' }).getByRole('link').all();
 assert.equal(links.length, 7);
 assert.deepEqual(await Promise.all(links.map(link => link.getAttribute('href'))), ['/overview', '/monitoring', '/anomalies', '/incidents', '/investigations', '/maintenance', '/settings']);
 for (const link of links) assert.equal((await page.request.get(`${web}${await link.getAttribute('href')}`)).status(), 200);
 assert.equal(await page.locator('.fm-metrics').evaluate(element => getComputedStyle(element).gridTemplateColumns.split(' ').length), 4);
 const expected = [actual.anomalies, actual.active_incidents, actual.investigations.completed, actual.investigations.failed].map(String);
 assert.deepEqual(await page.locator('.fm-metric strong').allTextContents(), expected);
 for (const [severity, count] of Object.entries(actual.severity_distribution)) {
  if (severity === 'normal') continue; // Normal observations are not detected anomalies.
  const legend = page.locator('.fm-legend>div').filter({ has: page.getByText(severity, { exact: true }) });
  assert.equal(await legend.locator('b').innerText(), String(count));
 }
 for (const state of ['completed', 'failed', 'running', 'queued']) {
  assert.equal(await page.locator('.fm-bar-column').filter({ has: page.getByText(state, { exact: true }) }).locator('.fm-bar-value').innerText(), String(actual.investigations[state]));
 }
 const jobs = [...actual.recent].sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at)).slice(0, 5);
 assert.equal(await page.locator('.fm-recent tbody tr').count(), jobs.length);
 assert.deepEqual(await page.locator('.fm-recent time').evaluateAll(elements => elements.map(element => element.dateTime)), jobs.map(job => job.created_at));
 for (const job of jobs) assert.equal(await page.getByRole('link', { name: `View Report ${job.investigation_id}`, exact: true }).getAttribute('href'), `/investigations/${job.investigation_id}`);
 const before = reads;
 await page.getByRole('button', { name: 'Refresh', exact: true }).click();
 await page.waitForFunction(() => document.querySelector('.fm-refresh')?.textContent === 'Refresh');
 assert.equal(reads, before + 1);
 if (actual.demo) {
  await page.getByRole('link', { name: 'Explore AI Demo' }).click();
  await page.getByRole('heading', { name: 'Guided Demo · Saved results' }).waitFor();
  await page.getByRole('heading', { name: `Historical result · ${actual.demo.investigation_id}` }).waitFor();
  await page.goto(`${web}/overview`);
  await page.getByText('API connected', { exact: true }).waitFor();
 }
 if (jobs.length) {
  await page.getByRole('link', { name: `View Report ${jobs[0].investigation_id}`, exact: true }).click();
  await page.waitForURL(`**/investigations/${jobs[0].investigation_id}`);
  await page.goto(`${web}/overview`);
  await page.getByText('API connected', { exact: true }).waitFor();
 }
 const screenshots = process.env.OVERVIEW_SCREENSHOT_DIR;
 if (screenshots) { await mkdir(screenshots, { recursive: true }); await page.screenshot({ path: `${screenshots}/overview-desktop.png`, fullPage: true }); }
 for (const [width, columns] of [[1100, 2], [768, 2], [390, 1]]) {
  await page.setViewportSize({ width, height: 950 });
  assert.equal(await page.locator('.fm-metrics').evaluate(element => getComputedStyle(element).gridTemplateColumns.split(' ').length), columns);
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
 }
 await page.getByRole('button', { name: 'Open navigation menu' }).click();
 await page.getByRole('link', { name: 'Settings', exact: true }).click();
 await page.waitForURL('**/settings');
 await page.goto(`${web}/overview`); await page.getByText('API connected', { exact: true }).waitFor();
 // Charts mount on viewport entry; exercise both on mobile before visual capture.
 await page.locator('.fm-charts .fm-panel').first().scrollIntoViewIfNeeded();
 await page.locator('.fm-donut svg').waitFor();
 await page.locator('.fm-charts .fm-panel').last().scrollIntoViewIfNeeded();
 await page.locator('.fm-bar-value').first().waitFor();
 if (screenshots) { await page.evaluate(() => scrollTo(0, 0)); await page.screenshot({ path: `${screenshots}/overview-mobile.png`, fullPage: true }); }
 offline = true;
 await page.getByRole('button', { name: 'Refresh', exact: true }).click();
 await page.getByText('API unavailable', { exact: true }).waitFor();
 await page.getByRole('alert').filter({ hasText: 'Showing previously loaded values' }).waitFor();
 await page.reload();
 await page.getByText('API unavailable', { exact: true }).waitFor();
 assert.equal(await page.locator('.fm-metric').count(), 0);
 offline = false; overview = { ...actual, recent: [], demo: null };
 await page.getByRole('button', { name: 'Try again', exact: true }).click();
 await page.getByText('No investigations yet. Create an incident and start an AI investigation to see results here.', { exact: true }).waitFor();
 assert.ok(await page.getByRole('button', { name: 'Explore AI Demo', exact: true }).isDisabled());
 await page.getByText('No verified saved demo available.', { exact: true }).waitFor();
 assert.deepEqual(errors, []); assert.ok(methods.every(method => method === 'GET'));
 console.log('PASS: real KPI/severity/status/recent data; seven sidebar links; actual timestamp order; report/demo navigation; GET-only refresh; unavailable/stale and empty states; 4/2/1 responsive grid and mobile menu; no browser errors.');
} finally { await browser.close(); }
