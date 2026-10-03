import { spawn } from "node:child_process";

// Build a separate production bundle against the intercepted test origin.
// The developer's .env and regular .next build are never modified.
const next = "node_modules/next/dist/bin/next";
const build = spawn(process.execPath, [next, "build"], { stdio: "inherit", env: process.env });
build.on("error", () => process.exit(1));
build.on("exit", (code) => {
  if (code !== 0) process.exit(code ?? 1);
  const server = spawn(process.execPath, [next, "start", "--hostname", "127.0.0.1", "--port", "3100"], { stdio: "inherit", env: process.env });
  server.on("error", () => process.exit(1));
  server.on("exit", (status) => process.exit(status ?? 1));
});
