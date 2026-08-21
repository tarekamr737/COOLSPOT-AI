type TileContext = { params: Promise<{ z: string; x: string; y: string }> };

function parseTileCoordinate(value: string): number | null {
  if (!/^\d+$/.test(value)) return null;
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) ? parsed : null;
}

export async function GET(_request: Request, context: TileContext): Promise<Response> {
  const raw = await context.params;
  const z = parseTileCoordinate(raw.z);
  const x = parseTileCoordinate(raw.x);
  const y = parseTileCoordinate(raw.y);
  if (z === null || x === null || y === null || z > 19) {
    return Response.json({ detail: "Invalid basemap tile" }, { status: 400 });
  }
  const limit = 2 ** z;
  if (x >= limit || y >= limit) {
    return Response.json({ detail: "Basemap tile is outside the zoom grid" }, { status: 400 });
  }

  try {
    const upstream = await fetch(`https://tile.openstreetmap.org/${z}/${x}/${y}.png`, {
      headers: { "User-Agent": "COOLSPOT-AI/0.1 urban-heat-planning-demo" },
      cache: "force-cache",
      next: { revalidate: 86_400 },
    });
    if (!upstream.ok) {
      return Response.json({ detail: "Basemap provider is unavailable" }, { status: 502 });
    }
    return new Response(upstream.body, {
      headers: {
        "Content-Type": "image/png",
        "Cache-Control": "public, max-age=86400, stale-while-revalidate=604800",
      },
    });
  } catch {
    return Response.json({ detail: "Basemap provider is unavailable" }, { status: 502 });
  }
}
