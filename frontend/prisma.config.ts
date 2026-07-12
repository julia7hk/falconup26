import { config as loadEnv } from "dotenv"
import { expand as expandEnv } from "dotenv-expand"
import { defineConfig } from "prisma/config"

// Schema source of truth is backend/alembic/. Use prisma db pull to
// introspect the live DB; nothing in prisma/ is hand-authored.
// dotenv-expand resolves $PGUSER:$PGPASSWORD-style interpolation
// in DATABASE_URL, matching how direnv loads it into the shell.
expandEnv(loadEnv({ path: "../.env" }))

// `prisma generate` runs in build-only contexts (Dockerfile, CI) that
// don't have a live DB, but Prisma still expects datasource.url to
// parse. Runtime queries always go through the PrismaPg adapter in
// lib/db.ts which reads DATABASE_URL itself, so this placeholder is
// only ever seen by the generator.
const databaseUrl =
  process.env["DATABASE_URL"] ||
  "postgresql://placeholder:placeholder@localhost:5432/placeholder"

export default defineConfig({
  schema: "prisma/schema.prisma",
  datasource: { url: databaseUrl },
})
