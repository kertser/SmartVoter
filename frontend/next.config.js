/** @type {import('next').NextConfig} */
const nextConfig = {
  // Enable standalone output for minimal production Docker image.
  // The Dockerfile.prod copies .next/standalone + .next/static + public.
  output: "standalone",
  // Disable every Next.js dev indicator / badge (including the "1 issue" webpack warning).
  // In Next.js 15.3+ `false` disables the whole overlay including the issues badge.
  devIndicators: false,
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  },
};

module.exports = nextConfig;

