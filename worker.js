const SNAPSHOT_PATH = "/studies/ongoing-studies.json";
const SNAPSHOT_ENVELOPE = "pbm-studies-encrypted-v1";
const encoder = new TextEncoder();

function response(body, status = 200, contentType = "text/html; charset=utf-8") {
  return new Response(body, {
    status,
    headers: {
      "Cache-Control": "no-store",
      "Content-Type": contentType,
      "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'",
      "Referrer-Policy": "no-referrer",
      "X-Content-Type-Options": "nosniff",
      "X-Robots-Tag": "noindex, nofollow, noarchive",
    },
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

  if (request.method !== "GET" && request.method !== "HEAD") {
    return response("Method not allowed.", 405, "text/plain; charset=utf-8");
  }

  const assetResponse = await context.next();
  if (url.pathname === SNAPSHOT_PATH && request.method === "GET" && assetResponse.ok) {
    try {
      const plaintext = await decryptSnapshot(await assetResponse.text(), env.PBM_STUDIES_DATA_KEY);
      return new Response(plaintext, {
        status: assetResponse.status,
        headers: {
          "Cache-Control": "public, max-age=300",
          "Content-Type": "application/json; charset=utf-8",
          "X-Robots-Tag": "noindex, nofollow, noarchive",
          "Referrer-Policy": "same-origin",
          "X-Content-Type-Options": "nosniff",
        },
      });
    } catch {
      return response("Study snapshot is unavailable.", 503, "text/plain; charset=utf-8");
    }
  }

  const headers = new Headers(assetResponse.headers);
  headers.set("Cache-Control", "no-store");
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
