import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  allowedDevOrigins: ["127.0.0.1"],
  ...(process.env.PLAYWRIGHT_PORT ? { distDir: ".next-playwright" } : {}),
  reactStrictMode: true
};

export default nextConfig;
