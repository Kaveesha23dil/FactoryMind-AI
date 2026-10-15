import assert from 'node:assert/strict';
import test from 'node:test';
import { DEFAULT_PREFERENCES, PREFERENCE_KEY, formatTimestamp, readPreferences, savePreferences, validatePreferences } from '../src/lib/preferences.ts';

test('reject malformed, unknown fields, invalid timezones and unsupported settings', () => {
  for (const value of [null, {}, { ...DEFAULT_PREFERENCES, appearance: 'invalid' }, { ...DEFAULT_PREFERENCES, timeZone: 'Factory/Mind' }, { ...DEFAULT_PREFERENCES, secret: 'private' }]) assert.equal(validatePreferences(value), false);
  assert.equal(validatePreferences({ ...DEFAULT_PREFERENCES, timeZone: 'Asia/Colombo' }), true);
});
test('timezone and regional preferences change genuine timestamps only', () => {
  const p = { ...DEFAULT_PREFERENCES, dateFormat: 'iso', timeFormat: '24h', timeZone: 'Asia/Colombo' };
  assert.equal(formatTimestamp('2026-01-31T23:00:00Z', p), '2026-02-01, 04:30:00');
  assert.equal(formatTimestamp('record-index', p), 'record-index');
  assert.match(formatTimestamp('2026-01-31T23:00:00Z', { ...p, dateFormat: 'day-first', timeZone: 'UTC' }), /31\/01\/2026/);
});
test('preferences round trip through browser storage; denied writes fail', () => {
  const storage = new Map();
  globalThis.window = { dispatchEvent() {} };
  globalThis.localStorage = { getItem: key => storage.get(key) ?? null, setItem: (key, value) => storage.set(key, value) };
  const prefs = { ...DEFAULT_PREFERENCES, appearance: 'dark', density: 'compact' };
  savePreferences(prefs);
  assert.deepEqual(readPreferences(), prefs);
  assert.equal(storage.size, 1);
  assert.ok(storage.has(PREFERENCE_KEY));
  globalThis.localStorage.setItem = () => { throw new Error('Storage denied'); };
  assert.throws(() => savePreferences(DEFAULT_PREFERENCES), /Storage denied/);
  storage.set(PREFERENCE_KEY, 'corrupt');
  assert.deepEqual(readPreferences(), DEFAULT_PREFERENCES);
  delete globalThis.window; delete globalThis.localStorage;
});
