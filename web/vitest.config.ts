import { defineConfig } from "vitest/config";

// Kept apart from vite.config.ts so the production build needs nothing from the
// test runner: the Dockerfile copies vite.config.ts and never this file.
export default defineConfig({
  test: {
    environment: "jsdom",
    include: ["tests/**/*.test.ts"],
  },
});
