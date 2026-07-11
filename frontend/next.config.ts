import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        // Forward all /api/* to FastAPI, except /api/auth/* which is
        // handled by Better Auth's Next.js route handler.
        source: "/api/:path((?!auth/).*)*",
        destination: `${process.env.NEXT_PUBLIC_FASTAPI_SERVER || "http://localhost:40401"}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
