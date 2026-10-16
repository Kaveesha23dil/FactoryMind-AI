import test from 'node:test';
import assert from 'node:assert/strict';
import { portableAuthorization, sessionCookie } from '../src/lib/portableProxyPolicy.ts';
test('portable proxy requires an actual user cookie, never a shared visitor secret', () => {
 assert.equal(portableAuthorization(null), null);
 assert.equal(portableAuthorization('X-User-ID=presenter'), null);
 assert.equal(sessionCookie('fm_session=malicious header'), null);
 const token = 'eyJheader.eyJpayload.signature';
 assert.equal(portableAuthorization(`other=value; fm_session=${token}; preference=light`), `Bearer ${token}`);
});
