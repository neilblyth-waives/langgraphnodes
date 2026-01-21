# Frontend Dockerfile for Supervisor Agent System
FROM nginx:alpine

# Copy static files
COPY . /usr/share/nginx/html

# Expose port
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost/ || exit 1

