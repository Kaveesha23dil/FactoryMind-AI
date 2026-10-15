/* Run against an isolated API with AI_PROVIDER=scripted. No mutation endpoints are called.
 * PLAYWRIGHT_MODULE points to an existing Playwright installation; no new dependency.
 * SETTINGS_WEB_URL and SETTINGS_API_URL select the local test servers.
 */
import assert from 'node:assert/strict';
import { pathToFileURL } from 'node:url';
import { mkdir } from 'node:fs/promises';
const modulePath = process.env.PLAYWRIGHT_MODULE;
const { chromium } = await import(modulePath ? pathToFileURL(`${modulePath}/index.mjs`).href : 'playwright');
const web = process.env.SETTINGS_WEB_URL || 'http://localhost:3000';
const api = process.env.SETTINGS_API_URL || 'http://127.0.0.1:8000';
const key = 'factorymind.preferences.v1';
(async () => {
 const browser = await chromium.launch({ channel: 'msedge', headless: true });
 try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 }, reducedMotion: 'reduce' });
  const errors = []; page.on('pageerror', error => errors.push(error.message));
  const settingsResponse = await fetch(`${api}/api/settings`);
  assert.equal(settingsResponse.status, 200);
  const settings = await settingsResponse.json();
  const system = await (await fetch(`${api}/api/settings/system`)).json();
  let failure = false; let delay = 0; const methods = [];
  await page.route('**/api/settings{,/**}', async route => {
   methods.push(route.request().method());
   if (delay) await new Promise(resolve => setTimeout(resolve, delay));
   if (failure) return route.fulfill({ status: 503, json: { detail: 'Unavailable' } });
   return route.fulfill({ json: route.request().url().endsWith('/system') ? system : settings });
  });
  delay = 700;
  await page.goto(`${web}/settings`);
  await page.getByRole('status', { name: 'Loading settings' }).waitFor();
  await page.getByRole('heading', { name: 'Workspace information' }).waitFor();
  delay = 0;
  const categories = ['General', 'AI Configuration', 'Anomaly Detection', 'Notifications', 'Data Management', 'Security & Access', 'System Information'];
  for (const name of categories) {
   await page.getByRole('navigation', { name: 'Settings categories' }).getByRole('button', { name, exact: true }).click();
   await page.getByRole('heading', { name, exact: true }).waitFor();
  }
  await page.getByRole('button', { name: 'Notifications', exact: true }).click();
  assert.equal(await page.getByRole('switch').count(), 6);
  for (const toggle of await page.getByRole('switch').all()) assert.ok(await toggle.isDisabled());
  await page.getByRole('button', { name: 'General', exact: true }).click();
  await page.getByLabel('Timezone', { exact: true }).fill('Invalid/Factory');
  assert.equal(await page.getByLabel('Timezone', { exact: true }).getAttribute('aria-invalid'), 'true');
  assert.ok(await page.getByRole('button', { name: 'Save changes', exact: true }).isDisabled());
  await page.getByLabel('Timezone', { exact: true }).fill('Asia/Colombo');
  await page.getByLabel('Color theme').selectOption('dark');
  await page.getByLabel('Display density').selectOption('compact');
  let warned = false;
  page.once('dialog', async dialog => { warned = true; await dialog.dismiss(); });
  await page.getByRole('link', { name: 'Overview', exact: true }).click();
  assert.ok(warned); assert.ok(page.url().endsWith('/settings'));
  await page.getByRole('button', { name: 'Save changes', exact: true }).click();
  await page.getByText('Preferences saved in this browser.', { exact: true }).waitFor();
  assert.equal(await page.locator('html').getAttribute('data-theme'), 'dark');
  assert.equal(await page.locator('html').getAttribute('data-density'), 'compact');
  await page.reload();
  await page.getByRole('heading', { name: 'Workspace information' }).waitFor();
  assert.equal(await page.getByLabel('Color theme').inputValue(), 'dark');
  assert.equal(await page.getByLabel('Timezone', { exact: true }).inputValue(), 'Asia/Colombo');
  const screenshotDir = process.env.SETTINGS_SCREENSHOT_DIR;
  assert.equal(await page.getByLabel('Color theme').evaluate(element => getComputedStyle(element).backgroundColor), 'rgb(28, 42, 64)');
  if (screenshotDir) { await mkdir(screenshotDir, { recursive: true }); await page.evaluate(() => scrollTo(0, 0)); await page.screenshot({ path: `${screenshotDir}/settings-dark-desktop.png`, fullPage: true }); }
  assert.equal(JSON.parse(await page.evaluate(key => localStorage.getItem(key), key)).density, 'compact');
  await page.getByLabel('Color theme').selectOption('light');
  await page.getByRole('button', { name: 'Reset changes' }).click();
  assert.equal(await page.getByLabel('Color theme').inputValue(), 'dark');
  await page.getByLabel('Color theme').selectOption('system');
  await page.getByRole('button', { name: 'Save changes', exact: true }).click();
  await page.emulateMedia({ colorScheme: 'light' });
  await page.waitForFunction(() => document.documentElement.dataset.theme === 'light');
  if (screenshotDir) { await page.evaluate(() => scrollTo(0, 0)); await page.screenshot({ path: `${screenshotDir}/settings-light-desktop.png`, fullPage: true }); }
  await page.emulateMedia({ colorScheme: 'dark' });
  await page.waitForFunction(() => document.documentElement.dataset.theme === 'dark');
  await page.setViewportSize({ width: 390, height: 844 });
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  assert.ok(await page.getByRole('complementary', { name: 'Primary navigation' }).evaluate(element => element.getBoundingClientRect().right <= 1));
  if (screenshotDir) { await page.evaluate(() => scrollTo(0, 0)); await page.screenshot({ path: `${screenshotDir}/settings-dark-mobile.png`, fullPage: true }); }
  await page.getByRole('button', { name: 'System Information', exact: true }).click();
  failure = true;
  await page.getByRole('button', { name: 'Refresh status' }).click();
  await page.getByRole('alert').filter({ hasText: 'System status is unavailable' }).waitFor();
  assert.ok(await page.getByRole('button', { name: 'Copy diagnostic summary' }).isDisabled());
  await page.reload();
  await page.getByRole('alert').filter({ hasText: 'Settings could not be loaded' }).waitFor();
  failure = false;
  await page.getByRole('button', { name: 'Retry', exact: true }).click();
  await page.getByRole('heading', { name: 'Workspace information' }).waitFor();
  await page.evaluate(() => { Storage.prototype.setItem = () => { throw new Error('Storage denied'); }; });
  await page.getByLabel('Color theme').selectOption('light');
  await page.getByRole('button', { name: 'Save changes', exact: true }).click();
  await page.getByRole('alert').filter({ hasText: 'Storage denied' }).waitFor();
  assert.deepEqual(errors, []);
  assert.ok(methods.every(method => method === 'GET'));
  console.log('PASS: seven sections; loading/retry; disabled notifications; timezone validation; unsaved navigation warning; save/reset/reload persistence; Light/Dark/System; mobile overflow; API failure; denied storage; no browser errors; GET-only API calls.');
 } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
