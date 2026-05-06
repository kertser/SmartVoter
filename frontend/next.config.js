/** @type {import('next').NextConfig} */
const nextConfig = {
  // Enable standalone output for minimal production Docker image.
  // The Dockerfile.prod copies .next/standalone + .next/static + public.
  output: "standalone",
  // Hide the Next.js development toolbar/indicator (bottom-left icon)
  devIndicators: false,
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  },
};

module.exports = nextConfig;

