FROM python:3.12-slim
RUN apt-get update && apt-get install -y iproute2
RUN pip install requests
COPY gateway.py /app/gateway.py
CMD ["python", "/app/gateway.py"]