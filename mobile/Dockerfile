FROM python:3.12-slim
RUN apt-get update && apt-get install -y iproute2
RUN pip install requests
COPY mobile.py /app/mobile.py
CMD ["python", "/app/mobile.py"]