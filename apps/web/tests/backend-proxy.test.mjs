import test from "node:test";
import assert from "node:assert/strict";
import { allowedBackendPath, configuredBackend, trustedWriteOrigin, boundedBody } from "../src/lib/backendProxyPolicy.ts";

test("proxy blocks worker routes and traversal", () => {
  assert.ok(allowedBackendPath(["api", "incidents", "INC-123"]));
  for (const path of [["api", "investigations", "INV-123", "process"], ["api", ".."], ["api", "images%2F.."], ["http:", "evil"]]) {
    assert.equal(allowedBackendPath(path), false);
  }
});
test("backend target must be a fixed HTTPS origin", () => {
  assert.ok(configuredBackend("https://backend.run.app"));
  for (const url of ["http://metadata.google.internal", "https://user:password@evil.com", "https://backend.run.app/path", "https://backend.run.app?url=evil"]) {
    assert.equal(configuredBackend(url), null);
  }
});
test("writes require the configured origin", () => {
  assert.ok(trustedWriteOrigin("http://localhost:8080", "http://localhost:8080"));
  assert.equal(trustedWriteOrigin(null, "https://web.run.app"), false);
  assert.equal(trustedWriteOrigin("https://evil.example", "https://web.run.app"), false);
});
test("body size is bounded even without a content-length header", async () => {
  assert.equal(await boundedBody(new Request("https://web.run.app", {method:"POST",body:"oversized"}), 3), null);
  const body = await boundedBody(new Request("https://web.run.app", {method:"POST",body:"ok"}), 3);
  assert.equal(new TextDecoder().decode(body), "ok");
});
