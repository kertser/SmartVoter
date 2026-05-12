/** @type {import('next').NextConfig} */
const nextConfig = {
  // Enable standalone output for minimal production Docker image.
  output: "standalone",
  // Disable every Next.js dev indicator / badge.
  devIndicators: false,
};

module.exports = nextConfig;
