const allowedGetPath = /^(pilot|candidates|data-status|methodology|layers\/(heat|persistence|exposure|vulnerability)|sites\/[A-Za-z0-9:_-]+)$/;

type RouteContext = { params: Promise<{ path: string[] }> };

function apiBaseUrl(): URL {
  const raw =
    process.env.API_BASE_URL ??
    process.env.NEXT_PUBLIC_API_BASE_URL ??
    "http://127.0.0.1:8000";
  const url = new URL(raw);
  if (!/^https?:$/.test(url.protocol)) {
    throw new Error("API_BASE_URL must use HTTP or HTTPS");
  }
  return url;
}

async function proxy(request: Request, context: RouteContext): Promise<Response> {
  const { path } = await context.params;
  const joinedPath = path.join("/");
  const isOptimizePost = request.method === "POST" && joinedPath === "optimize";
  const isAllowedGet = request.method === "GET" && allowedGetPath.test(joinedPath);
  if (!isOptimizePost && !isAllowedGet) {
    return Response.json({ detail: "Unsupported COOLSPOT API route" }, { status: 404 });
  }

  const upstreamUrl = new URL(`/v1/${joinedPath}`, apiBaseUrl());
  try {
    const upstream = await fetch(upstreamUrl, {
      method: request.method,
      body: isOptimizePost ? await request.text() : undefined,
      headers: isOptimizePost ? { "Content-Type": "application/json" } : undefined,
      cache: "no-store",
    });
    return new Response(upstream.body, {
      status: upstream.status,
      headers: { "Content-Type": upstream.headers.get("Content-Type") ?? "application/json" },
    });
  } catch {
    return Response.json(
      { detail: "The COOLSPOT API is unavailable. Start the FastAPI service and retry." },
      { status: 502 },
    );
  }
}

export const GET = proxy;
export const POST = proxy;
