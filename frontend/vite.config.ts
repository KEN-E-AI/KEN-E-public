import { defineConfig, loadEnv, Plugin } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";
import fs from "fs";

// Custom plugin to handle SPA fallback for client-side routing
const spaFallbackPlugin = (): Plugin => ({
  name: "spa-fallback",
  configureServer(server) {
    server.middlewares.use((req, res, next) => {
      if (req.url) {
        // Check if request is for a file (has extension at the end of the path)
        const isFileRequest = /\.[^/]+$/.test(req.url);
        // Check if it's a Vite internal request
        const isViteRequest =
          req.url.startsWith("/@") || req.url.startsWith("/node_modules");
        // Check if it's an API request (adjust pattern based on your API routes)
        const isApiRequest = req.url.startsWith("/api/");

        // If it's not a file, Vite internal, or API request, serve index.html
        if (!isFileRequest && !isViteRequest && !isApiRequest) {
          req.url = "/index.html";
        }
      }
      next();
    });
  },
});

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
        const value = valueParts.join("=").replace(/^["']|["']$/g, "");
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
    plugins: [react(), spaFallbackPlugin()],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
    },
    test: {
      setupFiles: ["./src/test/setup.ts"],
      globals: true,
      environment: "jsdom",
      exclude: ["e2e/**", "**/node_modules/**"],
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
