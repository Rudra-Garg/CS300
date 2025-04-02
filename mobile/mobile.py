import os
import time
import requests
import json
import random
import numpy as np
from prometheus_client import start_http_server, make_wsgi_app
from shared_modules.client_module import ClientModule
from flask import Flask
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from shared_modules.metrics import *

app = Flask(__name__)

# Add health check endpoint
@app.route('/health')
def health_check():
    return 'healthy', 200


# Add metrics endpoint to the Flask app
app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {
    '/metrics': make_wsgi_app()
})

# --- Configuration ---
gateway_name = os.getenv('GATEWAY')
gateway_url = f'http://{gateway_name}:8000/' if gateway_name else None
print(f"--- Mobile Configuration ---")
print(f"Gateway URL: {gateway_url}")
print(f"--------------------------")
# ---

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
            print("No data to send")
            return None

        for attempt in range(self.max_retries):
            start_time_gw = time.time()
            try:
                response = self.session.post(self.gateway_url, 
                                           json={"eeg_data": data},
                                           timeout=(5, 10))  # (connect, read) timeouts
                
                response.raise_for_status()
                request_time = time.time() - start_time_gw
                GATEWAY_REQUEST_LATENCY.set(request_time)

                try:
                    ack_data = response.json()
                    print(f"Received ACK from Gateway: {ack_data}. RTT: {request_time:.3f}s")
                    return ack_data # Return the ACK/status
                except json.JSONDecodeError:
                    print(f"Received non-JSON ACK from Gateway (Status: {response.status_code}). RTT: {request_time:.3f}s")
                    return {"status_code": response.status_code} # Return status code

            except requests.exceptions.RequestException as e:
                print(f"Attempt {attempt + 1}/{self.max_retries} failed: {str(e)}")
                GATEWAY_REQUEST_FAILURES.inc()
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))  # Exponential backoff
                continue
            except Exception as e:
                print(f"Unexpected error: {str(e)}")
                GATEWAY_REQUEST_FAILURES.inc()
                return None
        
        print("Failed to send data after all retries")
        GATEWAY_REQUEST_FAILURES.inc()
        return None

# Initialize components
sensor = SensorSimulator(transmission_time=0.1, sampling_rate=250)
client_module = ClientModule() 
gateway_connector = GatewayConnector(gateway_url)

if __name__ == '__main__':
    print(f"Mobile client started - connecting to gateway at {gateway_url}")
    
    # Start Flask server
    from threading import Thread
    flask_thread = Thread(target=lambda: app.run(host='0.0.0.0', port=9090, debug=False, use_reloader=False), daemon=True)
    flask_thread.start()
    
    while True:
        try:
            # Generate and process EEG data
            raw_eeg_data = sensor.generate_eeg_data()
            if raw_eeg_data:
                # Process data through client module
                processed_data = client_module.process_eeg(raw_eeg_data)
                if processed_data:
                    EEG_DATA_PROCESSED.inc()
                    # Send to gateway and handle response
                    response = gateway_connector.send_data(processed_data)
                    if response:
                        client_module.update_concentration_display(response)
            
            
        except KeyboardInterrupt:
            print("\nShutting down mobile client...")
            break
        except Exception as e:
            print(f"FATAL Error in main loop: {type(e).__name__} - {str(e)}")
            import traceback
            print(traceback.format_exc())
            time.sleep(5)
        
        time.sleep(0.05)