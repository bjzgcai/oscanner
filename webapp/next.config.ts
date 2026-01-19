import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Export the dashboard as static assets so it can be bundled into the Python package
  // and served directly by the FastAPI backend (no Node/npm runtime required).
  output: "export",
  basePath: "/dashboard",
  trailingSlash: true,
  // Avoid turbopack "inferred workspace root" warnings when multiple lockfiles exist on disk.
  turbopack: {
    root: __dirname,
  },
  images: {
    unoptimized: true,
  },
};

export default nextConfig;
