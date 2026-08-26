import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    const apiBaseUrl =
      process.env.BACKEND_URL ??
      process.env.API_BASE_URL ??
      "http://127.0.0.1:8000";
    return [
      { source: "/health", destination: `${apiBaseUrl}/health` },
      { source: "/v1/:path*", destination: `${apiBaseUrl}/v1/:path*` },
    ];
  },
};

export default nextConfig;
