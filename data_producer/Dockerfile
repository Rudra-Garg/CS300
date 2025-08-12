FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY eeg_eye_state.csv .
COPY data_producer.py .
CMD ["python", "data_producer.py"]