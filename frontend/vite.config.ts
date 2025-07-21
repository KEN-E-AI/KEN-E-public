import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";
import fs from "fs";

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  // Check if we have a resolved secrets file
  const resolvedEnvPath = path.resolve(__dirname, ".env.resolved");
  const hasResolvedSecrets = fs.existsSync(resolvedEnvPath);

  // Load environment variables
  let env = loadEnv(mode, process.cwd(), "");

  // If we have resolved secrets, use them for both dev and build
  if (hasResolvedSecrets) {
    console.log("Loading resolved secrets from .env.resolved");
    const resolvedContent = fs.readFileSync(resolvedEnvPath, "utf8");
    const resolvedLines = resolvedContent.split("\n");

    for (const line of resolvedLines) {
      if (line.trim() && !line.startsWith("#")) {
        const [key, ...valueParts] = line.split("=");
        const value = valueParts.join("=");
        if (key && value) {
          env[key] = value;
        }
      }
    }
  }

  return {
    server: {
      host: "::",
      port: 8080,
    },
    plugins: [react()],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
    },
    test: {
      setupFiles: ["./src/test/setup.ts"],
      globals: true,
      environment: "jsdom",
    },
    // Use resolved environment file if available
    envDir: hasResolvedSecrets ? __dirname : undefined,
    define: {
      // Manually define resolved environment variables when using resolved secrets
      ...(hasResolvedSecrets
        ? Object.keys(env)
            .filter((key) => key.startsWith("VITE_"))
            .reduce(
              (acc, key) => {
                acc[`import.meta.env.${key}`] = JSON.stringify(env[key]);
                return acc;
              },
              {} as Record<string, string>,
            )
        : {}),
    },
  };
});
