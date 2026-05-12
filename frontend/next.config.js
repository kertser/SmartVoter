/** @type {import('next').NextConfig} */
const nextConfig = {
  // Enable standalone output for minimal production Docker image.
  output: "standalone",
  // Disable every Next.js dev indicator / badge.
  devIndicators: false,
  // Proxy /api/* to the backend container server-side.
  // The browser only ever talks to port 3000 — backend port stays private.
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.BACKEND_URL || "http://localhost:8000"}/api/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
