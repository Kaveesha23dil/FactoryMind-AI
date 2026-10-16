/* Execute the actual Route Handler source with mocked network/ADC; no live auth. */
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import { createRequire } from 'node:module';
import ts from 'typescript';
const require = createRequire(import.meta.url);
const token = 'eyJheader.eyJpayload.signature';
const environment = { FACTORYMIND_DEPLOYMENT_TARGET: 'render', FACTORYMIND_BACKEND_URL: 'https://backend.example', FACTORYMIND_WEB_ORIGIN: 'https://frontend.example', FACTORYMIND_SUPABASE_URL: 'https://auth.example', FACTORYMIND_SUPABASE_ANON_KEY: 'public-test-key' };
function load(relative, fetch, env = environment) {
 const loadedModule = { exports: {} };
 const source = readFileSync(new URL(relative, import.meta.url), 'utf8');
 const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
 const context = { module: loadedModule, exports: loadedModule.exports, process: { env }, Request, Response, Headers, URL, Buffer, Uint8Array, TextDecoder, AbortSignal, fetch,
  require: name => {
   if (name === '@/lib/backendProxyPolicy') return load('../src/lib/backendProxyPolicy.ts', fetch, env);
   if (name === '@/lib/portableProxyPolicy') return load('../src/lib/portableProxyPolicy.ts', fetch, env);
   if (name === 'google-auth-library') return { GoogleAuth: class { async getIdTokenClient() { throw new Error('ADC must not be used for portable auth'); } } };
   return require(name);
  } };
 vm.runInNewContext(code, context);
 return loadedModule.exports;
}
const context = { params: Promise.resolve({ path: ['api', 'incidents'] }) };
test('proxy rejects anonymous calls, worker access and cross-origin writes before network', async () => {
 const network = async () => { throw new Error('Network must not run'); };
 const route = load('../src/app/api/backend/[...path]/route.ts', network);
 assert.equal((await route.GET(new Request('https://frontend.example/api/backend/api/incidents'), context)).status, 401);
 assert.equal((await route.POST(new Request('https://frontend.example/api/backend/api/incidents', { method: 'POST', headers: { origin: 'https://attacker.example', cookie: `fm_session=${token}` } }), context)).status, 403);
 assert.equal((await route.POST(new Request('https://frontend.example/api/backend/api/investigations/INV-A/process', { method: 'POST' }), { params: Promise.resolve({ path: ['api', 'investigations', 'INV-A', 'process'] }) })).status, 403);
});
test('proxy forwards only the signed-in user token; spoofed identity and service headers ignored', async () => {
 let called = false;
 const route = load('../src/app/api/backend/[...path]/route.ts', async (url, init) => {
  called = true; assert.equal(url.href, 'https://backend.example/api/incidents');
  assert.equal(init.headers.get('Authorization'), `Bearer ${token}`);
  assert.equal(init.headers.get('X-User-ID'), null);
  assert.equal(init.headers.get('X-Serverless-Authorization'), null);
  return Response.json({ items: [] });
 });
 const response = await route.GET(new Request('https://frontend.example/api/backend/api/incidents', { headers: { cookie: `fm_session=${token}`, Authorization: 'Bearer attacker', 'X-User-ID': 'presenter' } }), context);
 assert.equal(response.status, 200); assert.ok(called);
 assert.equal(response.headers.get('cache-control'), 'private, no-store');
});
test('session login returns an HttpOnly Secure user cookie, never tokens in JSON', async () => {
 const route = load('../src/app/api/session/route.ts', async url => url.includes('/auth/v1/token') ? Response.json({ access_token: token, expires_in: 3600 }) : Response.json({ authenticated: true }));
 const response = await route.POST(new Request('https://frontend.example/api/session', { method: 'POST', headers: { origin: environment.FACTORYMIND_WEB_ORIGIN }, body: JSON.stringify({ email: 'invited@example.test', password: 'test-only' }) }));
 assert.equal(response.status, 200);
 assert.deepEqual(await response.json(), { authenticated: true });
 const cookie = response.headers.get('set-cookie');
 assert.match(cookie, /HttpOnly/i); assert.match(cookie, /Secure/i); assert.match(cookie, /SameSite=lax/i);
});
test('workspace refusal issues no session; login/logout reject cross-site origins', async () => {
 const route = load('../src/app/api/session/route.ts', async url => url.includes('/auth/v1/token') ? Response.json({ access_token: token }) : Response.json({ detail: 'Not a member' }, { status: 403 }));
 const login = await route.POST(new Request('https://frontend.example/api/session', { method: 'POST', headers: { origin: environment.FACTORYMIND_WEB_ORIGIN }, body: JSON.stringify({ email: 'outsider@example.test', password: 'test-only' }) }));
 assert.equal(login.status, 403); assert.equal(login.headers.get('set-cookie'), null);
 assert.equal((await route.DELETE(new Request('https://frontend.example/api/session', { method: 'DELETE', headers: { origin: 'https://attacker.example' } }))).status, 403);
 const logout = await route.DELETE(new Request('https://frontend.example/api/session', { method: 'DELETE', headers: { origin: environment.FACTORYMIND_WEB_ORIGIN } }));
 assert.equal(logout.status, 200); assert.match(logout.headers.get('set-cookie'), /Max-Age=0/);
});

