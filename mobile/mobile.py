import os
import time
import requests
import json
import random
import numpy as np
import logging.config
import yaml
from prometheus_client import Counter, Gauge, start_http_server
from client_module import ClientModule

# Load logging configuration
with open('/app/config/logging.yaml', 'r') as f:
    config = yaml.safe_load(f)
    # Ensure log directory exists
    log_dir = '/app/logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    config['handlers']['file']['filename'] = os.path.join(log_dir, 'app.log')
    logging.config.dictConfig(config)

logger = logging.getLogger('mobile')

# Prometheus metrics
EEG_DATA_PROCESSED = Counter('eeg_data_processed_total', 'Total number of EEG data points processed')
GATEWAY_REQUEST_LATENCY = Gauge('gateway_request_latency_seconds', 'Gateway request latency in seconds')
GATEWAY_REQUEST_FAILURES = Counter('gateway_request_failures_total', 'Total number of failed gateway requests')

# Start Prometheus metrics server
start_http_server(9090)

gateway = os.getenv('GATEWAY')
url = f'http://{gateway}:8000/'

class SensorSimulator:
    """Simulate EEG Sensor with realistic data generation"""
    def __init__(self, transmission_time=5, sampling_rate=250):
        self.transmission_time = transmission_time
        self.last_transmission_time = 0
        self.sampling_rate = sampling_rate
        self.base_amplitude = 50  # Base amplitude for EEG waves
        self.noise_level = 0.1    # Noise level for simulation

    def generate_eeg_data(self):
        """Generate simulated EEG data with alpha waves and noise"""
        current_time = time.time()
        if current_time - self.last_transmission_time >= self.transmission_time:
            self.last_transmission_time = current_time
            
            # Generate time points
            t = np.linspace(0, self.transmission_time, int(self.sampling_rate * self.transmission_time))
            
            # Generate alpha waves (8-13 Hz)
            alpha_freq = 10  # Hz
            alpha_wave = self.base_amplitude * np.sin(2 * np.pi * alpha_freq * t)
            
            # Add noise
            noise = np.random.normal(0, self.base_amplitude * self.noise_level, len(t))
            eeg_signal = alpha_wave + noise
            
            # Package data
            return {
                "eeg_values": eeg_signal.tolist(),
                "timestamp": current_time,
                "sampling_rate": self.sampling_rate
            }
        return None

class GatewayConnector:
    """Handles communication with the Gateway"""
    def __init__(self, gateway_url, max_retries=3, retry_delay=1):
        self.gateway_url = gateway_url
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'EEGMobileClient/1.0'
        })

    def send_data(self, data):
        """Send data to gateway with retry mechanism"""
        if not data:
            logger.info("No data to send")
            return None

        for attempt in range(self.max_retries):
            try:
                response = self.session.post(self.gateway_url, 
                                           json={"eeg_data": data},
                                           timeout=(5, 10))  # (connect, read) timeouts
                
                response.raise_for_status()
                result = response.json()
                
                if 'error' in result:
                    print(f"Gateway error: {result['error']['message']}")
                    return None
                    
                return result
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"Attempt {attempt + 1}/{self.max_retries} failed: {str(e)}")
                GATEWAY_REQUEST_FAILURES.inc()
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))  # Exponential backoff
                continue
            except Exception as e:
                logger.error(f"Unexpected error: {str(e)}")
                GATEWAY_REQUEST_FAILURES.inc()
                return None
        
        logger.error("Failed to send data after all retries")
        GATEWAY_REQUEST_FAILURES.inc()
        return None

# Initialize components
sensor = SensorSimulator(transmission_time=5, sampling_rate=250)
client_module = ClientModule()
gateway_connector = GatewayConnector(url)

if __name__ == '__main__':
    logger.info(f"Mobile client started - connecting to gateway at {url}")
    
    while True:
        try:
            # Generate and process EEG data
            raw_eeg_data = sensor.generate_eeg_data()
            if raw_eeg_data:
                # Process data through client module
                start_time = time.time()
                processed_data = client_module.process_eeg(raw_eeg_data)
                if processed_data:
                    EEG_DATA_PROCESSED.inc()
                    # Send to gateway and handle response
                    response = gateway_connector.send_data(processed_data)
                    if response:
                        request_time = time.time() - start_time
                        GATEWAY_REQUEST_LATENCY.set(request_time)
                        client_module.update_concentration_display(response)
            
            time.sleep(0.1)  # Prevent CPU overload
            
        except KeyboardInterrupt:
            print("\nShutting down mobile client...")
            break
        except Exception as e:
            print(f"Error in main loop: {str(e)}")
            time.sleep(1)  # Delay before retry