# Authentication — Architecture & Concepts

Implementation: **Prisma** (typed database client for Next.js server-side
code) + **Better Auth** with Prisma adapter (same library as kkulgag).
Better Auth is the standard self-hosted auth library for Next.js as of
2026 — it absorbed Auth.js/NextAuth and succeeded the deprecated Lucia.
Free, self-hosted, you own your data in your own Postgres.

Prisma gives the Next.js server side a typed database client — auto-
complete, build-time type checking, and a generated client that mirrors
the Postgres schema. Better Auth uses Prisma as its adapter to read/write
auth tables. Prisma also enables future server components that query the
DB directly (like kkulgag does).

## Why auth is needed

The app is publicly deployed at `falconup.julia7hk.com` with zero
authentication. There is one shared `portfolio_holding` table with no
`user_id` — anyone who visits the URL can view, add, edit, and delete
holdings. Auth fixes three problems at once:

1. **Security** — the app is live and anyone can modify portfolio data.
2. **Multi-user** — retrofitting `user_id` later is painful. Doing it
   now means multi-user is a natural extension, not a rewrite.
3. **Project goals** — primary goal is learning/resume, secondary is
   personal use, tertiary is multi-user/monetization. Auth serves all
   four.

## How auth works (conceptual)

### Password hashing

When a user registers, their password is never stored directly. It's run
through a one-way hash function (bcrypt) that produces a jumbled string:

    "mypassword123"  →  bcrypt  →  "$2b$12$LJ3m4ks9fj..."

On login, the typed password is hashed again and compared to the stored
hash. If the database is stolen, attackers get useless hashes, not
passwords. Bcrypt is intentionally slow (~100ms per hash) — fine for one
login, impossible for brute-forcing millions of guesses.

### Sessions

After successful login, the server creates a session — a random token
stored in a `session` table row linked to the user. This is like a
concert wristband: you prove your identity once (password), get a
wristband (session token), and flash it at every door after that. The
session has an expiry time. When it expires or the user logs out, the
row is deleted.

### Cookies

The session token travels between browser and server via a cookie — the
browser attaches it to every request automatically. Key cookie flags:

- **httpOnly** — JavaScript cannot read it, so XSS attacks can't steal
  the token
- **Secure** — only sent over HTTPS
- **SameSite=Lax** — browser won't send it from other websites (CSRF
  protection)

### Multi-tenancy

Every row in `portfolio_holding` gets a `user_id` column. Every query
adds `WHERE user_id = <logged-in user>`. User A never sees User B's
holdings.

## Architecture: Better Auth + FastAPI

Better Auth is a TypeScript library that runs on the Next.js side. It
handles registration, login, logout, password hashing, session creation,
and cookie management. But portfolio data lives in FastAPI — so FastAPI
also needs to know who's logged in.

The solution: **shared session table**. Both Next.js (Better Auth) and
FastAPI read from the same Postgres `session` table. When FastAPI
receives a request, it reads the session cookie, looks up the token in
the `session` table, and resolves the `user_id`.

```
┌──────────────────────────────────────────────────────────┐
│ Browser                                                  │
│  Cookie: better-auth.session_token=abc123xyz             │
└──────────┬────────────────────────────┬──────────────────┘
           │                            │
           ▼                            ▼
┌─────────────────────┐    ┌─────────────────────────────┐
│ Next.js (frontend)  │    │ FastAPI (backend)            │
│                     │    │                              │
│ Better Auth handles │    │ Reads cookie → looks up      │
│ /sign-in, /sign-up, │    │ session in DB → resolves     │
│ session creation,   │    │ user_id → scopes portfolio   │
│ cookie management   │    │ queries by user_id           │
└────────┬────────────┘    └──────────────┬──────────────┘
         │                                │
         ▼                                ▼
┌──────────────────────────────────────────────────────────┐
│ Postgres (shared)                                        │
│                                                          │
│ user         → id, email, name, password hash            │
│ session      → token, user_id, expires_at                │
│ account      → provider credentials                      │
│ portfolio_holding → user_id FK, symbol_id, shares, cost  │
└──────────────────────────────────────────────────────────┘
```

## Request flow

```
1. User visits site → not logged in → redirect to /sign-in
2. User submits email + password
3. Better Auth (Next.js) hashes password, checks DB → match
4. Better Auth creates session row in DB, sets httpOnly cookie
5. User adds a holding → frontend calls POST /api/portfolio/holdings
6. FastAPI reads cookie → looks up session in Postgres → finds user_id
7. FastAPI inserts into portfolio_holding with user_id
8. User logs out → session row deleted, cookie cleared
9. Different user logs in → different user_id → sees empty portfolio
```

## Better Auth tables (camelCase)

Better Auth expects these tables with camelCase column names:

- `"user"` — `id` (text PK), `name`, `email` (unique), `"emailVerified"`,
  `image`, `"createdAt"`, `"updatedAt"`, `role`, `banned`, `"banReason"`,
  `"banExpires"`
- `session` — `id` (text PK), `token` (unique), `"userId"` (FK → user,
  CASCADE), `"expiresAt"`, `"createdAt"`, `"updatedAt"`, `"ipAddress"`,
  `"userAgent"`, `"impersonatedBy"`
- `account` — `id` (text PK), `"accountId"`, `"providerId"`, `"userId"`
  (FK → user, CASCADE), `password`, `"accessToken"`, `"refreshToken"`,
  `"idToken"`, `"accessTokenExpiresAt"`, `"refreshTokenExpiresAt"`,
  `scope`, `"createdAt"`, `"updatedAt"`
- `verification` — `id` (text PK), `identifier`, `value`, `"expiresAt"`,
  `"createdAt"`, `"updatedAt"`

## Security decisions

- **httpOnly cookies** over localStorage — XSS can't read the token.
- **bcrypt** for password hashing — intentionally slow, brute-force
  resistant. Better Auth uses this under the hood.
- **Server-side session validation on every request** — FastAPI's
  `get_current_user` checks the session table, not a client-side token.
- **SameSite=Lax + Secure** cookie flags — CSRF protection without a
  separate token.
