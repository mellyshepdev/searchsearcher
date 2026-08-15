import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Emit a self-contained server (.next/standalone) with a traced, minimal
  // node_modules. This is what lets the Docker runtime stage ship without the
  // build toolchain — see Dockerfile.
  output: "standalone",
};

export default nextConfig;
