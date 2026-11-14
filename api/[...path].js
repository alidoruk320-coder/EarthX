const ALLOWED_API_PATHS = [
  /^health$/,
  /^analyze-point$/,
  /^analyze-region$/,
  /^region-boundary$/,
  /^analyze-series$/,
  /^analyze-swot-lake$/,
  /^analyze-sea-level$/,
  /^cascade-correlation$/,
  /^biodiversity$/,
  /^impact\/exposure$/,
  /^tile-url\/[a-z0-9_-]+\/\d{4}$/i,
  /^change-tile-url\/[a-z0-9_-]+\/\d{4}\/\d{4}$/i,
];

async function handler(request) {
  const backendUrl = process.env.EARTHVERSE_BACKEND_URL;
  if (!backendUrl) {
    return Response.json(
      { detail: "EarthVerse data backend is not configured. Set EARTHVERSE_BACKEND_URL in Vercel." },
      { status: 503 },
    );
  }

  try {
    const incoming = new URL(request.url);
    const route = incoming.pathname.replace(/^\/api\//, "").replace(/\/$/, "");
    if (!ALLOWED_API_PATHS.some((pattern) => pattern.test(route))) {
      return Response.json({ detail: "Unknown EarthVerse API route." }, { status: 404 });
    }

    const backend = new URL(backendUrl);
    if (backend.protocol !== "https:" && backend.hostname !== "localhost" && backend.hostname !== "127.0.0.1") {
      return Response.json({ detail: "EARTHVERSE_BACKEND_URL must use HTTPS." }, { status: 500 });
    }
    const target = new URL(`/api/${route}${incoming.search}`, backend);
    const upstream = await fetch(target, {
      method: request.method,
      headers: {
        accept: request.headers.get("accept") || "application/json",
        ...(request.headers.get("content-type")
          ? { "content-type": request.headers.get("content-type") }
          : {}),
      },
      ...(["GET", "HEAD"].includes(request.method) ? {} : { body: request.body, duplex: "half" }),
      signal: AbortSignal.timeout(180_000),
    });
    const headers = new Headers();
    for (const name of ["content-type", "cache-control", "content-disposition"]) {
      const value = upstream.headers.get(name);
      if (value) headers.set(name, value);
    }
    return new Response(upstream.body, { status: upstream.status, headers });
  } catch (error) {
    const timedOut = error?.name === "TimeoutError";
    return Response.json(
      { detail: timedOut ? "EarthVerse data backend timed out." : "EarthVerse data backend is unavailable." },
      { status: timedOut ? 504 : 502 },
    );
  }
}

export const GET = handler;
export const HEAD = handler;
export const POST = handler;
export const PUT = handler;
export const PATCH = handler;
export const DELETE = handler;
