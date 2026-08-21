import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    return [
      { source: "/health", destination: "http://127.0.0.1:8000/health" },
      { source: "/v1/:path*", destination: "http://127.0.0.1:8000/v1/:path*" },
    ];
  },
};

export default nextConfig;
