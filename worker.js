function response(body, status = 200) {
  return new Response(body, {
    status,
    headers: {
      "Cache-Control": "no-store",
      "Content-Type": "text/plain; charset=utf-8",
      "X-Robots-Tag": "noindex, nofollow, noarchive",
      "X-Content-Type-Options": "nosniff",
      "Referrer-Policy": "same-origin",
    },
  });
}

function isStudiesPath(pathname) {
  return pathname === "/studies" || pathname === "/studies/" || pathname.startsWith("/studies/");
}

export async function handleStudiesRequest(context) {
  const { request } = context;
  const url = new URL(request.url);
  if (!isStudiesPath(url.pathname)) return context.next();

  if (request.method !== "GET" && request.method !== "HEAD") {
    return response("Method not allowed.", 405);
  }

  const assetResponse = await context.next();
  const headers = new Headers(assetResponse.headers);
  headers.set("X-Robots-Tag", "noindex, nofollow, noarchive");
  headers.set("X-Content-Type-Options", "nosniff");
  headers.set("Referrer-Policy", "same-origin");
  headers.set("Cache-Control", url.pathname === "/studies/ongoing-studies.json"
    ? "public, max-age=300"
    : "no-store");
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
