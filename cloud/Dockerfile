FROM nginx:latest

# Copy nginx configuration
COPY nginx.conf /etc/nginx/nginx.conf

# Create required log directories
RUN mkdir -p /var/log/nginx

# Install curl for health checks
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Expose port
EXPOSE 80

# Default command
CMD ["nginx", "-g", "daemon off;"]