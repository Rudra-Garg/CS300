FROM python:3.12-slim

LABEL maintainer="CS300 Team" component="proxy_py" version="1.0"

RUN apt-get update && apt-get install -y \
    iproute2 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY proxy_py/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY proxy_py/proxy_app.py ./
COPY proxy_py/entrypoint.sh ./
COPY shared_modules ./shared_modules 

RUN chmod +x ./entrypoint.sh

HEALTHCHECK --interval=30s --timeout=3s \
    CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["./entrypoint.sh"]
CMD ["python", "proxy_app.py"]
