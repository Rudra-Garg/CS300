FROM python:3.12-slim

LABEL maintainer="CS300 Team" component="cloud_py" version="1.0"

# No tc needed typically for cloud, but keep curl for healthcheck
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY cloud_py/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY cloud_py/cloud_app.py ./
# No entrypoint.sh needed unless adding features like delay simulation *within* cloud
COPY shared_modules ./shared_modules

HEALTHCHECK --interval=30s --timeout=3s \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["python", "cloud_app.py"]
