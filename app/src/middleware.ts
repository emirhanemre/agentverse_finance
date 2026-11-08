import { NextResponse, type NextRequest } from "next/server";

/**
 * Password gate for a deployed demo. Set SITE_PASSWORD (and optionally SITE_USER, default "pubhedge") in the
 * host's environment; the browser asks once and remembers it for the session. Unset, the gate is off, so local
 * dev needs nothing. It covers every page and every script file, so the bundle (and the API key inside it) is
 * only served to someone who knows the password.
 */
export function middleware(req: NextRequest) {
  const password = process.env.SITE_PASSWORD;
  if (!password) return NextResponse.next();
  const user = process.env.SITE_USER || "pubhedge";
  const auth = req.headers.get("authorization") ?? "";
  if (auth.startsWith("Basic ")) {
    try {
      const [u, ...rest] = atob(auth.slice(6)).split(":");
      if (u === user && rest.join(":") === password) return NextResponse.next();
    } catch {
      // malformed header: fall through to the challenge
    }
  }
  return new NextResponse("Password required", {
    status: 401,
    headers: { "WWW-Authenticate": 'Basic realm="Pub Hedge demo", charset="UTF-8"' },
  });
}

export const config = {
  // Everything except the favicon, so the challenge also guards the JavaScript bundle.
  matcher: ["/((?!favicon.ico).*)"],
};
