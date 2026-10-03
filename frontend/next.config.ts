import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  distDir: process.env.PITCHPREP_E2E === "1" ? ".next-e2e" : ".next",
};

export default nextConfig;
