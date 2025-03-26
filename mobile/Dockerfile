FROM python:3.12-slim
RUN apt-get update && apt-get install -y iproute2
RUN pip install requests

WORKDIR /app
COPY mobile.py /app/mobile.py
COPY client_module_impl.py /app/client_module_impl.py  

CMD ["python", "/app/mobile.py"]