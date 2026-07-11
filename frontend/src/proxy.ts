import { NextResponse, type NextRequest } from "next/server"

type SessionResponse = {
  user: { id: string; name: string; email: string }
} | null

export async function proxy(request: NextRequest) {
  const res = await fetch(
    new URL("/api/auth/get-session", request.nextUrl.origin),
    {
      headers: { cookie: request.headers.get("cookie") ?? "" },
      cache: "no-store",
    }
  )
  const session = (res.ok ? await res.json() : null) as SessionResponse

  if (!session) {
    const url = new URL("/sign-in", request.url)
    url.searchParams.set("redirect", request.nextUrl.pathname)
    return NextResponse.redirect(url)
  }

  return NextResponse.next()
}

export const config = {
  // No routes require auth redirect for now — the main page is public
  // and shows the portfolio section only when logged in. The backend
  // returns 401 on /api/portfolio/* without a session cookie.
  // Add protected routes here when needed (e.g. "/settings").
  matcher: [],
}
