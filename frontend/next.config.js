/** @type {import('next').NextConfig} */
const nextConfig = {
  // Enable standalone output for minimal production Docker image.
  output: "standalone",
  // Disable every Next.js dev indicator / badge.
  devIndicators: false,
  // /api/* requests are handled by app/api/[...path]/route.ts which proxies
  // them to the backend container, preserving all headers (incl. X-Admin-Password).
  // No rewrites needed here.
};

module.exports = nextConfig;
