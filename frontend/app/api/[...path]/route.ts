/**
 * Catch-all API proxy route.
 *
 * Forwards every /api/* request from the browser to the backend container,
 * preserving method, headers (including X-Admin-Password), and body.
 * This is more reliable than next.config.js rewrites in standalone mode.
 */
import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

async function proxy(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  const targetUrl = `${BACKEND_URL}/api/${path.join("/")}${req.nextUrl.search}`;

  // Forward all headers except host (which would confuse the backend)
  const headers = new Headers(req.headers);
  headers.delete("host");

  const init: RequestInit = {
    method: req.method,
    headers,
    // Don't forward body for GET/HEAD
    body: ["GET", "HEAD"].includes(req.method) ? undefined : req.body,
    // Required to forward the body stream
    // @ts-expect-error - duplex is not in the type defs yet
    duplex: "half",
  };

  try {
    const backendRes = await fetch(targetUrl, init);
    const resHeaders = new Headers(backendRes.headers);
    // Remove encoding headers that Next.js will re-apply
    resHeaders.delete("content-encoding");
    resHeaders.delete("transfer-encoding");

    return new NextResponse(backendRes.body, {
      status: backendRes.status,
      headers: resHeaders,
    });
  } catch (err) {
    console.error("[proxy] backend unreachable:", err);
    return NextResponse.json({ error: "Backend unreachable" }, { status: 502 });
  }
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
export const HEAD = proxy;
export const OPTIONS = proxy;

// Disable body parsing — we stream the raw body to the backend
export const dynamic = "force-dynamic";

