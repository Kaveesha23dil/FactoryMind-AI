/* Reads a reviewed local SQLite snapshot through a scripted-AI test API. GET only. */
import assert from 'node:assert/strict';
import { pathToFileURL } from 'node:url';
const modulePath = process.env.PLAYWRIGHT_MODULE;
const { chromium } = await import(modulePath ? pathToFileURL(`${modulePath}/index.mjs`).href : 'playwright');
const web = process.env.SETTINGS_WEB_URL || 'http://localhost:3000';
const api = process.env.SETTINGS_API_URL || 'http://127.0.0.1:8000';
const browser = await chromium.launch({ channel: 'msedge', headless: true });
try {
 const overview = await (await fetch(`${api}/api/submission/overview`)).json();
 assert.ok(overview.demo, 'Snapshot must contain an eligible historical saved report; never substitute a fixture.');
 const before = await (await fetch(`${api}/api/investigations/${overview.demo.investigation_id}`)).json();
 const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, reducedMotion: 'reduce' });
 const errors = []; const methods = [];
 page.on('pageerror', error => errors.push(error.message));
 await page.route('**/api/**', async route => {
  const method = route.request().method(); methods.push(method);
  assert.equal(method, 'GET', 'Saved walkthrough must not start reasoning or mutate data.');
  const incoming = new URL(route.request().url());
  const path = incoming.pathname.replace(/^\/api\/backend/, '');
  const response = await fetch(`${api}${path}${incoming.search}`);
  await route.fulfill({ status: response.status, body: await response.text(), contentType: 'application/json' });
 });
 await page.goto(`${web}/demo`);
 for (const name of ['Guided Demo · Saved results', '1. Abnormal benchmark observation', '2. Saved multi-agent interpretation', '3. Inspect stored evidence relationships', '4. Critic assessment', '5. Technician review draft', '6. Continue the investigation']) {
  await page.getByRole('heading', { name, exact: true }).waitFor();
 }
 await page.getByRole('heading', { name: 'Evidence graph', exact: true }).waitFor();
 assert.ok(await page.getByText(/no saved comparison is invented here/).count());
 if (overview.demo.audit.critic_attention_required) assert.ok(await page.getByText(/not an accepted diagnosis/).count());
 assert.ok(await page.getByText(/No ticket, approval or maintenance action has been executed/).count());
 const after = await (await fetch(`${api}/api/investigations/${overview.demo.investigation_id}`)).json();
 assert.deepEqual(after, before);
 assert.deepEqual(errors, []);
 assert.ok(methods.length >= 4 && methods.every(method => method === 'GET'));
 console.log('PASS: historical saved report, deterministic explanation, rendered graph, critic limitations, unapproved draft actions, honest missing-counterfactual state, GET-only, unchanged persisted report.');
} finally { await browser.close(); }
