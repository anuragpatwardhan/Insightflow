import path from "node:path";
import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: {
    // Mirrors the "@/*" path alias in tsconfig.json; vitest does not read
    // tsconfig paths on its own.
    alias: { "@": path.resolve(__dirname, ".") },
  },
  test: {
    // These cover the API client and the sparkline geometry, both plain
    // TypeScript. Component tests would need jsdom; there are none yet.
    environment: "node",
    include: ["lib/**/*.test.ts"],
  },
});
