import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const source = await readFile(new URL("../worker.js", import.meta.url), "utf8");
const worker = await import(`data:text/javascript;base64,${Buffer.from(source).toString("base64")}`);
const snapshot = JSON.stringify({ snapshot_status: "ready", records: [{ primary_id: "TEST-1" }] });

function context(url, { method = "GET", assetBody = "PUBLIC STUDY PAGE", assetStatus = 200 } = {}) {
  const request = new Request(url, { method });
  return {
    request,
    env: {},
    next: async () => new Response(assetBody, {
      status: assetStatus,
      headers: { "Content-Type": url.endsWith(".json") ? "application/json" : "text/html" },
    }),
  };
}

let result = await worker.handleStudiesRequest(context("https://example.test/studies/"));
assert.equal(result.status, 200);
assert.equal(await result.text(), "PUBLIC STUDY PAGE");
assert.equal(result.headers.get("Set-Cookie"), null);

result = await worker.handleStudiesRequest(context("https://example.test/studies/ongoing-studies.json", {
  assetBody: snapshot,
}));
assert.equal(result.status, 200);
assert.equal(await result.text(), snapshot);
assert.equal(result.headers.get("Cache-Control"), "public, max-age=300");
assert.equal(result.headers.get("Content-Type"), "application/json");
assert.equal(result.headers.get("X-Robots-Tag"), "noindex, nofollow, noarchive");

result = await worker.handleStudiesRequest(context("https://example.test/studies/", { method: "POST" }));
assert.equal(result.status, 405);
assert.equal(result.headers.get("Set-Cookie"), null);

result = await worker.handleStudiesRequest(context("https://example.test/about/"));
assert.equal(result.status, 200);
assert.equal(await result.text(), "PUBLIC STUDY PAGE");

result = await worker.default.fetch(new Request("https://example.test/studies/"), {
  ASSETS: { fetch: async () => new Response("PUBLIC STUDY PAGE") },
});
assert.equal(result.status, 200);
assert.equal(await result.text(), "PUBLIC STUDY PAGE");

const config = JSON.parse(await readFile(new URL("../wrangler.jsonc", import.meta.url), "utf8"));
assert.equal(config.main, "./worker.js");
assert.equal(config.assets.binding, "ASSETS");
assert.deepEqual(config.assets.run_worker_first, ["/studies", "/studies/*"]);

console.log("Public studies middleware checks passed.");
