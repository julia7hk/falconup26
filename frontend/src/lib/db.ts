import { PrismaPg } from "@prisma/adapter-pg"
import { PrismaClient } from "@/generated/prisma/client"

// Reuse the same client across hot-reloads in dev.
// In prod each Node process gets one fresh instance.
const globalForPrisma = globalThis as unknown as {
  prisma: PrismaClient | undefined
}

function makePrisma(): PrismaClient {
  return new PrismaClient({
    adapter: new PrismaPg({ connectionString: process.env.DATABASE_URL }),
  })
}

export const prisma = globalForPrisma.prisma ?? makePrisma()

if (process.env.NODE_ENV !== "production") {
  globalForPrisma.prisma = prisma
}
