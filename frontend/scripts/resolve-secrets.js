#!/usr/bin/env node

/**
 * Script to resolve Secret Manager secrets for frontend environment variables.
 * This runs at build time to fetch secrets and create a resolved .env file.
 */

import { SecretManagerServiceClient } from '@google-cloud/secret-manager';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

async function getSecret(secretPath) {
  try {
    const client = new SecretManagerServiceClient();
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
  const envPath = path.join(__dirname, '..', envFile);
  
  if (!fs.existsSync(envPath)) {
    console.error(`Environment file ${envFile} not found`);
    process.exit(1);
  }

  const envContent = fs.readFileSync(envPath, 'utf8');
  const lines = envContent.split('\n');
  const resolvedLines = [];

  for (const line of lines) {
    if (line.trim() === '' || line.startsWith('#')) {
      resolvedLines.push(line);
      continue;
    }

    const [key, value] = line.split('=', 2);
    if (!value) {
      resolvedLines.push(line);
      continue;
    }

    const cleanValue = value.trim();
    
    // Check if the value looks like a Secret Manager path
    if (cleanValue.startsWith('projects/') && 
        cleanValue.includes('/secrets/') && 
        cleanValue.includes('/versions/')) {
      
      try {
        console.log(`Resolving secret for ${key}...`);
        const secretValue = await getSecret(cleanValue);
        resolvedLines.push(`${key}=${secretValue}`);
      } catch (error) {
        console.error(`Failed to resolve secret for ${key}, using original value`);
        resolvedLines.push(line);
      }
    } else {
      resolvedLines.push(line);
    }
  }

  // Write resolved environment file
  const resolvedEnvPath = path.join(__dirname, '..', '.env.resolved');
  fs.writeFileSync(resolvedEnvPath, resolvedLines.join('\n'));
  console.log(`Resolved secrets written to .env.resolved`);
  
  // Also create a .env.local file for Vite to pick up during development
  const envLocalPath = path.join(__dirname, '..', '.env.local');
  
  // Only write secrets-related variables to .env.local to avoid conflicts
  const secretLines = resolvedLines.filter(line => {
    if (line.trim() === '' || line.startsWith('#')) return true;
    const [key] = line.split('=', 1);
    return key && (
      key.includes('API_KEY') || 
      key.includes('SECRET') || 
      key.includes('PASSWORD') || 
      key.includes('RECAPTCHA') ||
      key.includes('FIREBASE_API_KEY')
    );
  });
  
  if (secretLines.length > 1) { // More than just empty/comment lines
    fs.writeFileSync(envLocalPath, secretLines.join('\n'));
    console.log(`Secret environment variables written to .env.local`);
  }
}

// Get environment from command line argument
const environment = process.argv[2];
if (!environment) {
  console.error('Usage: node resolve-secrets.js <environment>');
  console.error('Example: node resolve-secrets.js .env.production');
  process.exit(1);
}

resolveSecrets(environment).catch((error) => {
  console.error('Error resolving secrets:', error);
  process.exit(1);
});