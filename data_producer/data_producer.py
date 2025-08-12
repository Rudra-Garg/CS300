import redis
import pandas as pd
import time
import json
import os

print("--- Data Producer Starting ---")
REDIS_HOST = os.getenv('REDIS_HOST', 'redis')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
DATA_FILE = 'eeg_eye_state.csv'
SAMPLING_RATE = 128  # This dataset's rate is 128 Hz
CHUNK_DURATION_S = 0.1 # Publish 100ms of data at a time
SAMPLES_PER_CHUNK = int(SAMPLING_RATE * CHUNK_DURATION_S)

# Connect to Redis
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
print(f"Connected to Redis at {REDIS_HOST}:{REDIS_PORT}")

# Load data from the 'AF3' channel of the CSV
eeg_dataset = pd.read_csv(DATA_FILE)['V1'].values
dataset_size = len(eeg_dataset)
print(f"Loaded {dataset_size} data points from the 'V1' channel.")

current_index = 0
while True:
    try:
        # Get the next chunk of data, looping if necessary
        start = current_index
        end = start + SAMPLES_PER_CHUNK
        if end > dataset_size:
            data_chunk = list(eeg_dataset[start:]) + list(eeg_dataset[:end % dataset_size])
        else:
            data_chunk = list(eeg_dataset[start:end])
        
        current_index = end % dataset_size

        # Prepare the message payload
        message = {
            "eeg_values": data_chunk,
            "sampling_rate": SAMPLING_RATE
        }
        
        # Publish the message to the 'eeg_stream' channel
        r.publish('eeg_stream', json.dumps(message))
        
        # Wait for the chunk duration to simulate real-time streaming
        time.sleep(CHUNK_DURATION_S)

    except redis.exceptions.ConnectionError as e:
        print(f"Redis connection error: {e}. Retrying in 5s...")
        time.sleep(5)
    except Exception as e:
        print(f"An error occurred: {e}")
        time.sleep(1)