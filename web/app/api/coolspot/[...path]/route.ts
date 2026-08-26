const allowedGetPath = /^(pilot|candidates|data-status|methodology|refresh\/status|layers\/(heat|persistence|exposure|vulnerability)|sites\/[A-Za-z0-9:_-]+(?:\/street-view)?)$/;

type RouteContext = { params: Promise<{ path: string[] }> };

function apiBaseUrl(): URL {
  const raw =
    process.env.BACKEND_URL ??
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
  const isAllowedPost =
    request.method === "POST" &&
    (joinedPath === "optimize" || joinedPath === "refresh" || /^sites\/[A-Za-z0-9:_-]+\/explanation$/.test(joinedPath));
  const isAllowedGet = request.method === "GET" && allowedGetPath.test(joinedPath);
  if (!isAllowedPost && !isAllowedGet) {
    return Response.json({ detail: "Unsupported COOLSPOT API route" }, { status: 404 });
  }

  const upstreamUrl = new URL(`/v1/${joinedPath}`, apiBaseUrl());
  try {
    const upstream = await fetch(upstreamUrl, {
      method: request.method,
      body: isAllowedPost ? await request.text() : undefined,
      headers: isAllowedPost
        ? {
            "Content-Type": "application/json",
            ...(joinedPath === "refresh"
              ? { "X-Refresh-Token": request.headers.get("X-Refresh-Token") ?? "" }
              : {}),
          }
        : undefined,
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
