FROM python:3.12-slim

# Add labels for better container identification
LABEL maintainer="CS300 Team" \
    component="mobile" \
    version="1.0"

# Install system dependencies
RUN apt-get update && apt-get install -y \
    iproute2 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r /app/requirements.txt

WORKDIR /app

# Copy application files
COPY mobile.py /app/
COPY client_module.py /app/
COPY metrics.py /app/

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Command to run
CMD ["python", "mobile.py"]