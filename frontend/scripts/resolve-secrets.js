#!/usr/bin/env node

/**
 * Script to resolve Secret Manager secrets for frontend environment variables.
 * This runs at build time to fetch secrets and create a resolved .env file.
 */

import { SecretManagerServiceClient } from "@google-cloud/secret-manager";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

async function getSecret(secretPath, serviceAccountPath) {
  try {
    const clientConfig = {};
    
    // If service account path is provided and exists, use it
    if (serviceAccountPath && fs.existsSync(serviceAccountPath)) {
      console.log(`Using service account: ${serviceAccountPath}`);
      clientConfig.keyFilename = serviceAccountPath;
    } else {
      console.log(`Using Application Default Credentials (service account not found at: ${serviceAccountPath})`);
    }
    
    const client = new SecretManagerServiceClient(clientConfig);
    const [version] = await client.accessSecretVersion({
      name: secretPath,
    });
    return version.payload.data.toString();
  } catch (error) {
    console.error(`Failed to retrieve secret ${secretPath}:`, error.message);
    throw error;
  }
}

async function resolveSecrets(envFile) {
  const envPath = path.join(__dirname, "..", envFile);

  if (!fs.existsSync(envPath)) {
    console.error(`Environment file ${envFile} not found`);
    process.exit(1);
  }

  // Determine which service account to use based on the environment file
  let serviceAccountPath = null;
  if (envFile.includes("development")) {
    serviceAccountPath = path.join(__dirname, "../../api/ken-e-dev.json");
  } else if (envFile.includes("staging")) {
    serviceAccountPath = path.join(__dirname, "../../api/ken-e-staging.json");
  } else if (envFile.includes("production")) {
    serviceAccountPath = path.join(__dirname, "../../api/ken-e-production.json");
  }

  if (serviceAccountPath && !fs.existsSync(serviceAccountPath)) {
    console.warn(`Service account file not found at: ${serviceAccountPath}`);
    console.warn(`Will fall back to Application Default Credentials`);
  }

  const envContent = fs.readFileSync(envPath, "utf8");
  const lines = envContent.split("\n");
  const resolvedLines = [];

  for (const line of lines) {
    if (line.trim() === "" || line.startsWith("#")) {
      resolvedLines.push(line);
      continue;
    }

    const [key, value] = line.split("=", 2);
    if (!value) {
      resolvedLines.push(line);
      continue;
    }

    const cleanValue = value.trim();

    // Check if the value looks like a Secret Manager path
    if (
      cleanValue.startsWith("projects/") &&
      cleanValue.includes("/secrets/") &&
      cleanValue.includes("/versions/")
    ) {
      try {
        console.log(`Resolving secret for ${key}...`);
        const secretValue = await getSecret(cleanValue, serviceAccountPath);
        resolvedLines.push(`${key}=${secretValue}`);
      } catch (error) {
        console.error(
          `Failed to resolve secret for ${key}, using original value`,
        );
        resolvedLines.push(line);
      }
    } else {
      resolvedLines.push(line);
    }
  }

  // Write resolved environment file
  const resolvedEnvPath = path.join(__dirname, "..", ".env.resolved");
  fs.writeFileSync(resolvedEnvPath, resolvedLines.join("\n"));
  console.log(`Resolved secrets written to .env.resolved`);

  // Also create a .env.local file for Vite to pick up during development
  const envLocalPath = path.join(__dirname, "..", ".env.local");

  // Only write secrets-related variables to .env.local to avoid conflicts
  const secretLines = resolvedLines.filter((line) => {
    if (line.trim() === "" || line.startsWith("#")) return true;
    const [key] = line.split("=", 1);
    return (
      key &&
      (key.includes("API_KEY") ||
        key.includes("SECRET") ||
        key.includes("PASSWORD") ||
        key.includes("RECAPTCHA") ||
        key.includes("FIREBASE_API_KEY"))
    );
  });

  if (secretLines.length > 1) {
    // More than just empty/comment lines
    fs.writeFileSync(envLocalPath, secretLines.join("\n"));
    console.log(`Secret environment variables written to .env.local`);
  }
}

// Get environment from command line argument
const environment = process.argv[2];
if (!environment) {
  console.error("Usage: node resolve-secrets.js <environment>");
  console.error("Example: node resolve-secrets.js .env.production");
  console.error("");
  console.error("Note: This script expects service account files to be located at:");
  console.error("  - api/ken-e-dev.json (for development)");
  console.error("  - api/ken-e-staging.json (for staging)");
  console.error("  - api/ken-e-production.json (for production)");
  process.exit(1);
}

console.log(`Resolving secrets for environment: ${environment}`);
resolveSecrets(environment).catch((error) => {
  console.error("Error resolving secrets:", error);
  console.error("");
  console.error("If you're seeing authentication errors, ensure you have either:");
  console.error("1. Service account JSON files in api/ directory:");
  console.error("   - ken-e-dev.json");
  console.error("   - ken-e-staging.json");
  console.error("   - ken-e-production.json");
  console.error("2. Or run: gcloud auth application-default login");
  process.exit(1);
});
