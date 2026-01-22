import type { NextConfig } from "next";
import { dirname, join } from "path";
import { fileURLToPath } from "url";

const thisDir = dirname(fileURLToPath(import.meta.url));

const isDev = process.env.NODE_ENV !== "production";
const backendUrl = process.env.NEXT_PUBLIC_API_SERVER_URL || "http://localhost:8000";

const nextConfig: NextConfig = {
  // Export the dashboard as static assets so it can be bundled into the Python package
  // and served directly by the FastAPI backend (no Node/npm runtime required).
  // Only use static export for production builds; dev mode needs rewrites for API proxy.
  ...(isDev ? {} : { output: "export" }),
  basePath: "/dashboard",
  trailingSlash: true,
  // Avoid turbopack "inferred workspace root" warnings when multiple lockfiles exist on disk.
  turbopack: {
    root: thisDir,
  },
  images: {
    unoptimized: true,
  },
  // Allow importing plugin views from repository root `plugins/` directory.
  // This is required for dynamic plugin view rendering in the dashboard.
  experimental: {
    externalDir: true,
  },
  // In dev mode, proxy /api/** requests to FastAPI backend (no CORS issues, no env var needed)
  ...(isDev
    ? {
        async rewrites() {
          return [
            {
              source: "/api/:path*",
              destination: `${backendUrl}/api/:path*`,
            },
          ];
        },
      }
    : {}),
  webpack: (config) => {
    // When importing TSX from outside `webapp/` (e.g. `../plugins/.../view/index.tsx`),
    // webpack's module resolution won't find `webapp/node_modules` by walking up from that file.
    // Add it explicitly so plugin views can import dependencies like `antd`.
    const webappNodeModules = join(thisDir, "node_modules");
    const mods = config?.resolve?.modules;
    if (Array.isArray(mods)) {
      config.resolve.modules = [webappNodeModules, ...mods];
    } else {
      config.resolve = config.resolve || {};
      config.resolve.modules = [webappNodeModules, "node_modules"];
    }
    return config;
  },
};

export default nextConfig;
