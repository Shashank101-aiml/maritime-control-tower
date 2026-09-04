# Build stage
FROM node:20-alpine as build

WORKDIR /app

# Install dependencies
COPY package.json package-lock.json ./
RUN npm install

# Copy source code and build
COPY . .

# Vite inlines import.meta.env.VITE_* at build time, not runtime -- so
# the backend origin has to be known here, not just at `docker run`.
# Defaults to src/config.js's own fallback (localhost:8000) when unset,
# so a plain `docker build` with no --build-arg still works.
ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

# Production stage
FROM nginx:alpine

# Copy built assets
COPY --from=build /app/dist /usr/share/nginx/html

# Expose port 80
EXPOSE 80

# Start Nginx
CMD ["nginx", "-g", "daemon off;"]
