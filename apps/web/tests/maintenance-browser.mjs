/* GET-only checks against genuine saved investigation data; empty/error states are browser-only. */
import assert from 'node:assert/strict';
import { pathToFileURL } from 'node:url';
import { readFile, mkdir } from 'node:fs/promises';
const modulePath = process.env.PLAYWRIGHT_MODULE;
const { chromium } = await import(modulePath ? pathToFileURL(`${modulePath}/index.mjs`).href : 'playwright');
const web = process.env.SETTINGS_WEB_URL || 'http://localhost:3000';
const api = process.env.SETTINGS_API_URL || 'http://127.0.0.1:8000';
const browser = await chromium.launch({ channel: 'msedge', headless: true });
try {
 const jobs = []; let offset = 0; let total = 0;
 do {
  const response = await fetch(`${api}/api/investigations?limit=100&offset=${offset}&status=completed`);
  assert.equal(response.status, 200);
  const page = await response.json(); total = page.total; jobs.push(...page.items); offset += page.items.length;
  assert.ok(page.items.length || !total);
 } while (offset < total);
 const genuine = [];
 for (const row of jobs.filter(job => job.provider === 'google')) {
  const job = await (await fetch(`${api}/api/investigations/${row.investigation_id}`)).json();
  if (job.report?.recommended_actions.length) genuine.push(job);
 }
 assert.ok(genuine.length, 'This browser acceptance test requires actual saved Google recommendations, never substituted fixtures.');
 const expected = genuine.reduce((count, job) => count + job.report.recommended_actions.filter(action => action.action.trim()).length, 0);
 const page = await browser.newPage({ viewport: { width: 1440, height: 1100 }, reducedMotion: 'reduce', acceptDownloads: true });
 const errors = []; const methods = [];
 page.on('pageerror', error => errors.push(error.message));
 page.on('console', message => { if (message.type() === 'error' && /hydrat|server rendered|didn.t match/i.test(message.text())) errors.push(message.text()); });
 let mode = 'real'; let reads = 0;
 await page.route('**/api/**', async route => {
  methods.push(route.request().method()); assert.equal(route.request().method(), 'GET');
  const incoming = new URL(route.request().url()); const path = incoming.pathname.replace(/^\/api\/backend/, '');
  if (path === '/api/investigations') reads++;
  if (mode === 'offline') return route.fulfill({ status: 503, json: { detail: 'Unavailable' } });
  if (mode === 'empty' && path === '/api/investigations') return route.fulfill({ json: { total: 0, limit: 100, offset: 0, returned: 0, items: [] } });
  const response = await fetch(`${api}${path}${incoming.search}`);
  await route.fulfill({ status: response.status, body: await response.text(), contentType: 'application/json' });
 });
 await page.goto(`${web}/maintenance`);
 await page.getByRole('heading', { name: 'Maintenance Review', exact: true }).waitFor();
 await page.locator('.mr-recommendation').first().waitFor();
 assert.equal(await page.locator('.mr-available strong').innerText(), String(expected));
 assert.equal(await page.locator('.mr-recommendation').count(), expected);
 assert.deepEqual(await page.locator('.mr-untracked').allTextContents(), ['Unavailable', 'Unavailable']);
 assert.equal(await page.getByRole('button', { name: /^(Approve|Reject|Create Ticket)$/i }).count(), 0);
 const card = page.locator('.mr-recommendation').first();
 const sourceId = await card.locator('.mr-card-top a').innerText();
 const original = await (await fetch(`${api}/api/investigations/${sourceId}`)).json();
 const evidence = await (await fetch(`${api}/api/investigations/${sourceId}/evidence`)).json();
 const inspectionText = await card.locator('h3').innerText();
 const action = original.report.recommended_actions.find(action => action.action === inspectionText);
 assert.ok(action);
 const hypotheses = original.report.hypotheses.filter(h => action.supporting_hypothesis_ids.includes(h.hypothesis_id));
 const ids = [...new Set(hypotheses.flatMap(h => h.supporting_evidence_ids))].filter(id => original.report.evidence_catalog.includes(id) && evidence.items.some(item => item.evidence_id === id));
 assert.ok((await card.locator('.mr-card-facts').innerText()).includes(`${ids.length} supporting evidence IDs`));
 await card.getByRole('button', { name: /^View Details / }).click();
 const detail = page.getByRole('region', { name: 'Inspection recommendation details' });
 await detail.waitFor();
 for (const heading of ['Investigation summary', 'Proposed inspection', 'Related hypotheses', 'Missing information', 'Critic verification notes']) await detail.getByRole('heading', { name: heading, exact: true }).waitFor();
 assert.equal(await detail.getByRole('link', { name: `Source ${sourceId}` }).getAttribute('href'), `/investigations/${sourceId}`);
 for (const id of ids) assert.ok(await detail.getByText(id, { exact: true }).count());
 const downloadPromise = page.waitForEvent('download');
 await detail.getByRole('button', { name: 'Download technician review draft' }).click();
 const download = await downloadPromise;
 assert.equal(download.suggestedFilename(), `${sourceId}-inspection-draft.txt`);
 const text = await readFile(await download.path(), 'utf8');
 assert.ok(text.includes(`Investigation: ${sourceId}`)); assert.ok(text.includes(action.action));
 assert.ok(text.includes('Technician review: __________  Approval: __________'));
 assert.ok(text.includes('This draft is not work authorization.'));
 const screenshots = process.env.MAINTENANCE_SCREENSHOT_DIR;
 if (screenshots) { await mkdir(screenshots, { recursive: true }); await page.evaluate(() => scrollTo(0, 0)); await page.screenshot({ path: `${screenshots}/maintenance-desktop.png`, fullPage: true }); }
 await page.getByRole('button', { name: 'Close details' }).click();
 assert.equal(await detail.count(), 0);
 const before = reads;
 await page.getByRole('button', { name: 'Refresh', exact: true }).click();
 await page.waitForFunction(() => !document.querySelector('.mr-loading'));
 assert.equal(reads, before + 1);
 await page.setViewportSize({ width: 390, height: 844 });
 assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
 await page.locator('.mr-recommendation').first().getByRole('button', { name: /^View Details / }).click();
 await detail.waitFor(); assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
 if (screenshots) { await page.evaluate(() => scrollTo(0, 0)); await page.screenshot({ path: `${screenshots}/maintenance-mobile.png`, fullPage: true }); }
 const after = await (await fetch(`${api}/api/investigations/${sourceId}`)).json(); assert.deepEqual(after, original);
 mode = 'offline'; await page.reload();
 await page.getByRole('alert').filter({ hasText: 'Unable to load saved recommendations' }).waitFor();
 assert.equal(await page.locator('.mr-available strong').innerText(), '—');
 assert.equal(await page.getByRole('heading', { name: 'No maintenance drafts available' }).count(), 0);
 mode = 'empty'; await page.getByRole('button', { name: 'Retry', exact: true }).click();
 await page.getByRole('heading', { name: 'No maintenance drafts available', exact: true }).waitFor();
 assert.equal(await page.locator('.mr-available strong').innerText(), '0');
 assert.equal(await page.locator('.mr-recommendation').count(), 0);
 assert.equal(await page.locator('.mr-empty').getByRole('link', { name: 'View AI Investigations' }).getAttribute('href'), '/investigations');
 assert.deepEqual(errors, []); assert.ok(methods.every(method => method === 'GET'));
 console.log(`PASS: ${expected} genuine saved recommendations; resolved evidence counts; critic detail; unsupported approval states/actions; draft download and blank approval; unchanged source; refresh; mobile; accurate offline/empty states; GET-only and no browser errors.`);
} finally { await browser.close(); }
