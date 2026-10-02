const COOKIE_NAME = "pbm_studies_session";
const SESSION_SECONDS = 60 * 60 * 24 * 30;
const SNAPSHOT_PATH = "/studies/ongoing-studies.json";
const SNAPSHOT_ENVELOPE = "pbm-studies-encrypted-v1";
const encoder = new TextEncoder();

function hex(bytes) {
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function signature(secret, message) {
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  return hex(new Uint8Array(await crypto.subtle.sign("HMAC", key, encoder.encode(message))));
}

function constantTimeEqual(left, right) {
  const length = Math.max(left.length, right.length);
  let difference = left.length ^ right.length;
  for (let index = 0; index < length; index += 1) {
    difference |= (left.charCodeAt(index) || 0) ^ (right.charCodeAt(index) || 0);
  }
  return difference === 0;
}

function response(body, status = 200, extraHeaders = {}) {
  return new Response(body, {
    status,
    headers: {
      "Cache-Control": "no-store",
      "Content-Type": "text/html; charset=utf-8",
      "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'",
      "Referrer-Policy": "no-referrer",
      "X-Content-Type-Options": "nosniff",
      "X-Robots-Tag": "noindex, nofollow, noarchive",
      ...extraHeaders,
    },
  });
}

function loginPage(invalid = false) {
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="noindex, nofollow, noarchive">
  <title>Private study database — Photobiomodulation Science</title>
  <style>
    :root { color-scheme: light; font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #263443; background: #f4f6f8; }
    * { box-sizing: border-box; }
    body { min-height: 100vh; margin: 0; display: grid; place-items: center; padding: 24px; }
    main { width: min(100%, 440px); padding: 34px; border: 1px solid #dce2e8; border-radius: 16px; background: #fff; box-shadow: 0 16px 48px #21324712; }
    .brand { margin: 0 0 30px; color: #243c59; font-size: .88rem; font-weight: 750; letter-spacing: .02em; }
    h1 { margin: 0; color: #243c59; font-size: 1.6rem; line-height: 1.2; }
    p { margin: 12px 0 22px; color: #5e6b79; line-height: 1.55; }
    label { display: grid; gap: 7px; color: #243c59; font-size: .9rem; font-weight: 700; }
    input { width: 100%; min-height: 48px; padding: 10px 12px; border: 1px solid #cbd4de; border-radius: 9px; color: #263443; font: inherit; }
    input:focus { outline: 3px solid #78a7d333; border-color: #4778a8; }
    button { width: 100%; min-height: 46px; margin-top: 16px; border: 0; border-radius: 9px; color: #fff; background: #243c59; font: inherit; font-weight: 750; cursor: pointer; }
    .error { margin: 0 0 14px; color: #a32632; font-weight: 650; }
    .foot { margin: 20px 0 0; font-size: .78rem; }
  </style>
</head>
<body>
  <main>
    <p class="brand">Photobiomodulation Science</p>
    <h1>Private study database</h1>
    <p>Enter the shared password to search the ongoing PBM study pilot.</p>
    ${invalid ? '<p class="error" role="alert">That password was not accepted. Please try again.</p>' : ""}
    <form method="post" action="/studies/" autocomplete="on">
      <input type="hidden" name="action" value="login">
      <label for="password">Password
        <input id="password" name="password" type="password" autocomplete="current-password" required autofocus>
      </label>
      <button type="submit">Open database</button>
    </form>
    <p class="foot">The records are a research registry snapshot. Confirm study details in the linked registry.</p>
  </main>
</body>
</html>`;
}

function readCookie(request) {
  const cookies = request.headers.get("Cookie") || "";
  for (const item of cookies.split(";")) {
    const separator = item.indexOf("=");
    if (separator < 0) continue;
    if (item.slice(0, separator).trim() === COOKIE_NAME) {
      return item.slice(separator + 1).trim();
    }
  }
  return "";
}

async function validSession(request, secret) {
  const token = readCookie(request);
  const separator = token.indexOf(".");
  if (separator < 1) return false;
  const expiry = Number(token.slice(0, separator));
  const now = Math.floor(Date.now() / 1000);
  if (!Number.isInteger(expiry) || expiry <= now || expiry > now + SESSION_SECONDS + 60) return false;
  const expected = await signature(secret, `pbm-studies-session:${expiry}`);
  return constantTimeEqual(expected, token.slice(separator + 1));
}

function withCookie(responseToWrap, cookie) {
  const headers = new Headers(responseToWrap.headers);
  headers.append("Set-Cookie", cookie);
  return new Response(responseToWrap.body, {
    status: responseToWrap.status,
    statusText: responseToWrap.statusText,
    headers,
  });
}

function isStudiesPath(pathname) {
  return pathname === "/studies" || pathname === "/studies/" || pathname.startsWith("/studies/");
}

function decodeBase64(value) {
  if (typeof value !== "string" || !/^[A-Za-z0-9+/]*={0,2}$/.test(value)) {
    throw new Error("Invalid encrypted snapshot");
  }
  return Uint8Array.from(atob(value), (character) => character.charCodeAt(0));
}

async function decryptSnapshot(envelopeText, dataKeyHex) {
  const envelope = JSON.parse(envelopeText);
  if (envelope.format !== SNAPSHOT_ENVELOPE || envelope.algorithm !== "AES-256-GCM") {
    throw new Error("Unsupported encrypted snapshot");
  }
  if (typeof dataKeyHex !== "string" || !/^[a-f0-9]{64}$/i.test(dataKeyHex)) {
    throw new Error("Study snapshot key is not configured");
  }
  const iv = decodeBase64(envelope.iv);
  const ciphertext = decodeBase64(envelope.ciphertext);
  if (iv.length !== 12 || ciphertext.length < 16) {
    throw new Error("Invalid encrypted snapshot");
  }
  const key = await crypto.subtle.importKey(
    "raw", Uint8Array.from(dataKeyHex.match(/../g), (byte) => parseInt(byte, 16)),
    { name: "AES-GCM" }, false, ["decrypt"],
  );
  return crypto.subtle.decrypt({ name: "AES-GCM", iv }, key, ciphertext);
}

export async function handleStudiesRequest(context) {
  const { request, env } = context;
  const url = new URL(request.url);
  if (!isStudiesPath(url.pathname)) return context.next();

  const secret = env.PBM_STUDIES_PASSWORD;
  if (typeof secret !== "string" || secret.length < 12) {
    return response("Study access is not configured.", 503);
  }

  const isEntry = url.pathname === "/studies" || url.pathname === "/studies/";
  if (request.method === "POST") {
    if (!isEntry) return response("Method not allowed.", 405, { Allow: "GET, HEAD" });
    let form;
    try {
      form = await request.formData();
    } catch {
      return response(loginPage(true), 400);
    }
    if (form.get("action") === "logout") {
      const redirect = Response.redirect(new URL("/studies/", request.url), 303);
      return withCookie(redirect, `${COOKIE_NAME}=; Path=/studies; Max-Age=0; HttpOnly; Secure; SameSite=Lax`);
    }
    const supplied = form.get("password");
    if (typeof supplied !== "string" || supplied.length > 1024) {
      return response(loginPage(true), 401);
    }
    const expected = await signature(secret, "pbm-studies-password-check");
    const actual = await signature(supplied, "pbm-studies-password-check");
    if (!constantTimeEqual(expected, actual)) return response(loginPage(true), 401);

    const expiry = Math.floor(Date.now() / 1000) + SESSION_SECONDS;
    const token = `${expiry}.${await signature(secret, `pbm-studies-session:${expiry}`)}`;
    const redirect = Response.redirect(new URL("/studies/", request.url), 303);
    return withCookie(
      redirect,
      `${COOKIE_NAME}=${token}; Path=/studies; Max-Age=${SESSION_SECONDS}; HttpOnly; Secure; SameSite=Lax`,
    );
  }

  if (request.method !== "GET" && request.method !== "HEAD") {
    return response("Method not allowed.", 405, { Allow: "GET, HEAD, POST" });
  }
  if (!(await validSession(request, secret))) {
    if (request.method === "HEAD") return response("", 401);
    return response(loginPage(), 401);
  }

  const assetResponse = await context.next();
  if (url.pathname === SNAPSHOT_PATH && request.method === "GET" && assetResponse.ok) {
    try {
      const plaintext = await decryptSnapshot(await assetResponse.text(), env.PBM_STUDIES_DATA_KEY);
      return new Response(plaintext, {
        status: assetResponse.status,
        headers: {
          "Cache-Control": "private, no-store",
          "Content-Type": "application/json; charset=utf-8",
          "X-Robots-Tag": "noindex, nofollow, noarchive",
          "Referrer-Policy": "same-origin",
          "X-Content-Type-Options": "nosniff",
        },
      });
    } catch {
      return response("Study snapshot is unavailable.", 503);
    }
  }
  const headers = new Headers(assetResponse.headers);
  headers.set("Cache-Control", "private, no-store");
  headers.set("X-Robots-Tag", "noindex, nofollow, noarchive");
  headers.set("Referrer-Policy", "same-origin");
  headers.set("X-Content-Type-Options", "nosniff");
  return new Response(assetResponse.body, {
    status: assetResponse.status,
    statusText: assetResponse.statusText,
    headers,
  });
}

export default {
  async fetch(request, env) {
    return handleStudiesRequest({
      request,
      env,
      next: () => env.ASSETS.fetch(request),
    });
  },
};
