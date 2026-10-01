import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { webcrypto } from "node:crypto";

globalThis.crypto ??= webcrypto;
const source = await readFile(new URL("../worker.js", import.meta.url), "utf8");
const worker = await import(`data:text/javascript;base64,${Buffer.from(source).toString("base64")}`);
const { encryptSnapshot } = await import("../scripts/encrypt_studies_snapshot.mjs");
const password = "test-only-password-123";
const dataKey = "0123456789abcdef".repeat(4);
const plaintextSnapshot = JSON.stringify({ snapshot_status: "ready", records: [{ primary_id: "TEST-1" }] });
const encryptedSnapshot = await encryptSnapshot(plaintextSnapshot, dataKey);

function context(url, { method = "GET", headers = {}, body, secret = password, key = dataKey, assetBody } = {}) {
  const request = new Request(url, { method, headers, body, redirect: "manual" });
  return {
    request,
    env: secret === null ? {} : { PBM_STUDIES_PASSWORD: secret, PBM_STUDIES_DATA_KEY: key },
    next: async () => new Response(assetBody || (url.endsWith("ongoing-studies.json") ? encryptedSnapshot : "PRIVATE STUDY DATA"), {
      status: 200,
      headers: { "Content-Type": "application/json", "Cache-Control": "public, max-age=3600" },
    }),
  };
}

let result = await worker.handleStudiesRequest(context("https://example.test/studies/"));
assert.equal(result.status, 401);
const unauthenticatedPage = await result.text();
assert.match(unauthenticatedPage, /Private study database/);
assert.doesNotMatch(unauthenticatedPage, new RegExp(password));

result = await worker.handleStudiesRequest(context("https://example.test/studies/ongoing-studies.json"));
assert.equal(result.status, 401);
assert.doesNotMatch(await result.text(), /PRIVATE STUDY DATA/);

const wrongForm = new FormData();
wrongForm.set("action", "login");
wrongForm.set("password", "incorrect");
result = await worker.handleStudiesRequest(context("https://example.test/studies/", { method: "POST", body: wrongForm }));
assert.equal(result.status, 401);
assert.match(await result.text(), /not accepted/);

const loginForm = new FormData();
loginForm.set("action", "login");
loginForm.set("password", password);
result = await worker.handleStudiesRequest(context("https://example.test/studies/", { method: "POST", body: loginForm }));
assert.equal(result.status, 303);
const setCookie = result.headers.get("Set-Cookie");
assert.match(setCookie, /HttpOnly/);
assert.match(setCookie, /Secure/);
assert.match(setCookie, /SameSite=Lax/);
assert.doesNotMatch(setCookie, new RegExp(password));
const cookie = setCookie.split(";")[0];

result = await worker.handleStudiesRequest(context("https://example.test/studies/ongoing-studies.json", {
  headers: { Cookie: cookie },
}));
assert.equal(result.status, 200);
assert.equal(await result.text(), plaintextSnapshot);
assert.equal(result.headers.get("Cache-Control"), "private, no-store");
assert.equal(result.headers.get("X-Robots-Tag"), "noindex, nofollow, noarchive");

const [cookieName, token] = cookie.split("=");
const tampered = `${cookieName}=${token.slice(0, -1)}0`;
result = await worker.handleStudiesRequest(context("https://example.test/studies/", {
  headers: { Cookie: tampered },
}));
assert.equal(result.status, 401);

const logoutForm = new FormData();
logoutForm.set("action", "logout");
result = await worker.handleStudiesRequest(context("https://example.test/studies/", {
  method: "POST",
  headers: { Cookie: cookie },
  body: logoutForm,
}));
assert.equal(result.status, 303);
assert.match(result.headers.get("Set-Cookie"), /Max-Age=0/);

result = await worker.handleStudiesRequest(context("https://example.test/studies/", { secret: null }));
assert.equal(result.status, 503);
assert.doesNotMatch(await result.text(), /PRIVATE STUDY DATA/);

result = await worker.handleStudiesRequest(context("https://example.test/studies/ongoing-studies.json", {
  headers: { Cookie: cookie },
  assetBody: "not encrypted study data",
}));
assert.equal(result.status, 503);
assert.doesNotMatch(await result.text(), /not encrypted study data/);

result = await worker.handleStudiesRequest(context("https://example.test/studies/ongoing-studies.json", {
  headers: { Cookie: cookie },
  key: "",
}));
assert.equal(result.status, 503);
assert.doesNotMatch(await result.text(), /PRIVATE STUDY DATA/);

assert.doesNotMatch(encryptedSnapshot, /TEST-1|test-only-password-123/);
const publicEnvelope = JSON.parse(await readFile(new URL("../dist/studies/ongoing-studies.json", import.meta.url), "utf8"));
assert.equal(publicEnvelope.format, "pbm-studies-encrypted-v1");
assert.equal(Object.hasOwn(publicEnvelope, "records"), false);
assert.doesNotMatch(JSON.stringify(publicEnvelope), /photobiomodulation|ongoing PBM/i);

result = await worker.handleStudiesRequest(context("https://example.test/about/"));
assert.equal(result.status, 200);
assert.equal(await result.text(), "PRIVATE STUDY DATA");

const config = JSON.parse(await readFile(new URL("../wrangler.jsonc", import.meta.url), "utf8"));
assert.equal(config.main, "./worker.js");
assert.equal(config.assets.binding, "ASSETS");
assert.deepEqual(config.assets.run_worker_first, ["/studies", "/studies/*"]);

const workerRequest = new Request("https://example.test/studies/ongoing-studies.json", {
  headers: { Cookie: cookie },
});
const deployedShape = await worker.default.fetch(workerRequest, {
  PBM_STUDIES_PASSWORD: password,
  PBM_STUDIES_DATA_KEY: dataKey,
  ASSETS: { fetch: async () => new Response(encryptedSnapshot) },
});
assert.equal(deployedShape.status, 200);
assert.equal(await deployedShape.text(), plaintextSnapshot);

console.log("Password and encrypted-snapshot middleware checks passed.");
