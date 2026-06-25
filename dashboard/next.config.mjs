/** @type {import('next').NextConfig} */
const nextConfig = {
  // The dashboard is fully static: every page reads the committed JSON snapshot
  // in `data/` at build time (SSG). No server runtime or external API needed,
  // so it deploys clean to Vercel as a static export-compatible app.
  reactStrictMode: true,
};

export default nextConfig;
