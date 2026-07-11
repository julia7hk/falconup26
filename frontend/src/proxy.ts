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
  // Protect the main app page. Sign-in/sign-up and API routes are public.
  matcher: ["/"],
}
