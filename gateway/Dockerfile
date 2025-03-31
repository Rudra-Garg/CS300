FROM python:3.12-slim

LABEL maintainer="CS300 Team" \
    component="gateway" \
    version="1.0"

RUN apt-get update && apt-get install -y \
    iproute2 \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r /app/requirements.txt

WORKDIR /app
COPY gateway.py /app/
COPY concentration_calculator_module.py /app/
COPY entrypoint.sh /app/entrypoint.sh 
RUN chmod +x /app/entrypoint.sh      


HEALTHCHECK --interval=30s --timeout=3s \
    CMD curl -f http://localhost:8000/health || exit 1

ENV PYTHONUNBUFFERED=1
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["python", "gateway.py"]