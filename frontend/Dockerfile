# Stage 1 - Build the React app
FROM node:18-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm install --legacy-peer-deps
# COPY .env .env
COPY . .
RUN npm run build

# Stage 2 - Serve built assets using nginx
FROM nginx:stable-alpine
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy custom nginx configuration for SPA routing
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port 8080 as configured in vite.config.ts
EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
