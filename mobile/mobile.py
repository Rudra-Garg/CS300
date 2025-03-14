import os
import time

import requests

gateway = os.getenv('GATEWAY')
url = f'http://{gateway}:8000/'

while True:
    try:
        response = requests.get(url)
        print(f"Received response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")
    time.sleep(5)
