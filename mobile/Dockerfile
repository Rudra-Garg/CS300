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
WORKDIR /app

COPY mobile/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY mobile/mobile.py ./
COPY mobile/entrypoint.sh ./
COPY shared_modules ./shared_modules 

RUN chmod +x ./entrypoint.sh

HEALTHCHECK --interval=30s --timeout=3s \
    CMD curl -f http://localhost:9090/health || exit 1

ENTRYPOINT ["./entrypoint.sh"]
CMD ["python", "mobile.py"]