import { defineConfig } from "vitest/config";
import { resolve } from "path";

export default defineConfig({
  test: {
    name: "integration",
    environment: "jsdom",
    setupFiles: ["../setup.ts"],
    include: ["**/*.test.tsx"],
    exclude: ["**/node_modules/**", "**/dist/**"],
    globals: true,
    css: true,
    reporters: ["verbose"],
    coverage: {
      provider: "v8",
      reporter: ["text", "html", "json"],
      exclude: [
        "node_modules/",
        "src/test/",
        "**/*.d.ts",
        "**/*.config.*",
        "**/coverage/**",
      ],
    },
    testTimeout: 30000, // Longer timeout for integration tests
    hookTimeout: 30000,
    pool: "threads",
    poolOptions: {
      threads: {
        singleThread: false,
        minThreads: 1,
        maxThreads: 4,
      },
    },
  },
  resolve: {
    alias: {
      "@": resolve(__dirname, "../../"),
    },
  },
});
