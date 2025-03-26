FROM python:3.12-slim
RUN apt-get update && apt-get install -y iproute2
RUN pip install requests

WORKDIR /app
COPY gateway.py /app/gateway.py
COPY concentration_calculator_module_impl.py /app/concentration_calculator_module_impl.py 

CMD ["python", "/app/gateway.py"]