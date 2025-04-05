import math
import os
import threading
import time
import requests
import json
import socket
import numpy as np
from flask import Flask
from werkzeug.middleware.dispatcher import DispatcherMiddleware
import traceback

from shared_modules.client_module import ClientModule
from shared_modules.concentration_calculator_module import ConcentrationCalculatorModule
from shared_modules.connector_module import ConnectorModule

from shared_modules.cpu_monitor import get_container_cpu_percent_non_blocking
from shared_modules.metrics import * # Imports Counters, Gauges etc.

MY_TIER = "mobile"

app = Flask(__name__)

# --- Metrics & Monitoring Setup ---
CPU_UTILIZATION = Gauge('cpu_utilization_percent', 'Current CPU utilization percentage', ['container_name'])
container_name = socket.gethostname()

def collect_cpu_metrics():
    while True:
        cpu_info = get_container_cpu_percent_non_blocking()
        if cpu_info:
            normalized_cpu = cpu_info.get('cpu_percent_normalized', math.nan)
            if not math.isnan(normalized_cpu): CPU_UTILIZATION.labels(container_name=container_name).set(normalized_cpu)
            else: CPU_UTILIZATION.labels(container_name=container_name).set(-1.0) # Indicate NaN
        else: CPU_UTILIZATION.labels(container_name=container_name).set(-2.0) # Indicate error getting info
        time.sleep(1) # Check frequency

def start_cpu_monitoring():
    cpu_thread = threading.Thread(target=collect_cpu_metrics, daemon=True)
    cpu_thread.start()
    print(f"Mobile ({container_name}): Background CPU monitoring started")

@app.route('/health')
def health_check():
    return 'healthy', 200

app.wsgi_app = DispatcherMiddleware(app.wsgi_app, { '/metrics': make_wsgi_app() })
# --- Configuration ---
gateway_name = os.getenv('GATEWAY')
gateway_url = f'http://{gateway_name}:8000/' if gateway_name else None
try:
    mobile_processing_level = int(os.getenv('MOBILE_PROCESSING_LEVEL', 1))
except ValueError:
    print(f"WARN ({container_name}): Invalid MOBILE_PROCESSING_LEVEL, defaulting to 1.")
    mobile_processing_level = 1
effective_mobile_processing_level = max(0, mobile_processing_level)

print(f"--- Mobile Configuration ({container_name}) ---")
print(f"Gateway URL: {gateway_url}")
print(f"Mobile Processing Level (Config): {mobile_processing_level}")
print(f"Mobile Processing Level (Effective): {effective_mobile_processing_level}")
print(f"------------------------------------------")
# ---

# --- Sensor Simulator (Keep as is) ---
class SensorSimulator:
    def __init__(self, transmission_time=0.1, sampling_rate=250):
        self.transmission_time = transmission_time
        self.last_transmission_time = 0
        self.sampling_rate = sampling_rate
        self.base_amplitude = 50
        self.noise_level = 0.1

    def generate_eeg_data(self):
        current_time = time.time()
        t = np.linspace(0, self.transmission_time, int(self.sampling_rate * self.transmission_time), endpoint=False)
        alpha_freq = 10
        alpha_wave = self.base_amplitude * np.sin(2 * np.pi * alpha_freq * t)
        noise = np.random.normal(0, self.base_amplitude * self.noise_level, len(t))
        eeg_signal = alpha_wave + noise
        return {
            "eeg_values": eeg_signal.tolist(),
            "timestamp": current_time,
            "sampling_rate": self.sampling_rate
        }
# ---

# --- Gateway Connector (Keep as is) ---
class GatewayConnector:
    def __init__(self, gateway_url, max_retries=3, retry_delay=1):
        self.gateway_url = gateway_url
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.session = requests.Session()
        self.session.headers.update({'Content-Type': 'application/json', 'User-Agent': f'EEGMobileClient/1.0 ({container_name})'})

    def send_data(self, data_to_send: dict):
        if not self.gateway_url:
            print(f"ERROR ({container_name}): Gateway URL not set.")
            return None
        if not data_to_send or "payload" not in data_to_send or "last_processed_level" not in data_to_send:
            print(f"ERROR ({container_name}): Invalid data structure for send_data: {data_to_send}")
            return None

        for attempt in range(self.max_retries):
            start_time_gw = time.time()
            try:
                response = self.session.post(self.gateway_url, json=data_to_send, timeout=(5, 10)) # 5s connect, 10s read
                request_time = time.time() - start_time_gw
                GATEWAY_REQUEST_LATENCY.set(request_time) # Gauge for RTT

                response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

                try:
                    ack_data = response.json()
                    print(f"Mobile ({container_name}): Received ACK/Response (L{ack_data.get('processed_up_to', 'N/A')}) from {gateway_name}. RTT: {request_time:.3f}s")
                    return ack_data
                except json.JSONDecodeError:
                    print(f"Mobile ({container_name}): Received non-JSON ACK from {gateway_name} (Status: {response.status_code}). RTT: {request_time:.3f}s")
                    return {"status": f"gateway_status_{response.status_code}"} # Return status info

            except requests.exceptions.Timeout:
                print(f"Mobile ({container_name}): Attempt {attempt + 1}/{self.max_retries} to {gateway_name} timed out.")
                GATEWAY_REQUEST_FAILURES.inc()
            except requests.exceptions.ConnectionError:
                print(f"Mobile ({container_name}): Attempt {attempt + 1}/{self.max_retries} connection to {gateway_name} failed.")
                GATEWAY_REQUEST_FAILURES.inc()
            except requests.exceptions.HTTPError as http_err:
                print(f"Mobile ({container_name}): Attempt {attempt + 1}/{self.max_retries} HTTP error from {gateway_name}: {http_err}")
                # Could potentially increment a different counter for server-side errors vs network errors
                GATEWAY_REQUEST_FAILURES.inc() # Count as failure for now
            except requests.exceptions.RequestException as e:
                print(f"Mobile ({container_name}): Attempt {attempt + 1}/{self.max_retries} generic request error to {gateway_name}: {type(e).__name__}")
                GATEWAY_REQUEST_FAILURES.inc()

            if attempt < self.max_retries - 1:
                time.sleep(self.retry_delay * (attempt + 1))
            else:
                print(f"Mobile ({container_name}): Failed to send data to {gateway_name} after all retries.")
                # Consider setting latency gauge to a high value or specific error code?
        return None # Failed after retries
# ---

# --- Initialize Modules Conditionally ---
client_module = None
concentration_calculator = None
connector_module = None

if effective_mobile_processing_level >= 1 and ClientModule:
    client_module = ClientModule()
    print(f"INFO ({container_name}): Client Module (L1) initialized on Mobile.")
if effective_mobile_processing_level >= 2 and ConcentrationCalculatorModule:
    concentration_calculator = ConcentrationCalculatorModule()
    print(f"INFO ({container_name}): Concentration Calculator Module (L2) initialized on Mobile.")
else:
    if effective_mobile_processing_level >= 2: print(f"WARN ({container_name}): L2 requested but module not found.")

if effective_mobile_processing_level >= 3 and ConnectorModule:
    if concentration_calculator: # Check dependency
        connector_module = ConnectorModule()
        print(f"INFO ({container_name}): Connector Module (L3) initialized on Mobile.")
    else:
        print(f"WARN ({container_name}): Cannot initialize Connector (L3) on Mobile without Calculator (L>=2). Degrading level.")
        effective_mobile_processing_level = min(effective_mobile_processing_level, 1) # Degrade gracefully
else:
    if effective_mobile_processing_level >= 3: print(f"WARN ({container_name}): L3 requested but module not found.")
# ---

# --- Initialize Sensor and Connector ---
sensor = SensorSimulator(transmission_time=0.1, sampling_rate=250)
gateway_connector = GatewayConnector(gateway_url)
# ---

if __name__ == '__main__':
    print(f"Mobile client started ({container_name}, Effective Level {effective_mobile_processing_level}) - connecting to gateway at {gateway_url}")
    start_cpu_monitoring()

    flask_thread = threading.Thread(target=lambda: app.run(host='0.0.0.0', port=9090, debug=False, use_reloader=False), daemon=True)
    flask_thread.start()

    last_send_attempt_time = 0
    send_interval = 0.1 # Target ~10Hz send rate

    while True:
        main_loop_start_time = time.time()
        try:
            raw_eeg_data = sensor.generate_eeg_data()
            if not raw_eeg_data: continue

            level_received = 0 # Input is always L0 for mobile
            current_data = raw_eeg_data
            level_processed_here = 0 # Track highest level processed *in this service*
            processing_error = False

            # --- Processing Pipeline ---
            # Only run modules if the effective level allows AND the data hasn't reached that level yet

            # Level 1: Client
            if not processing_error and level_received < 1 and effective_mobile_processing_level >= 1 and client_module:
                module_name = "client"
                try:
                    with MODULE_LATENCY.labels(tier=MY_TIER, module=module_name).time():
                        client_output = client_module.process_eeg(current_data)

                    if not client_output:
                        # Data discarded by client (quality)
                        processing_error = True # Stop processing this data point
                        # Metric EEG_DISCARDED_TOTAL incremented inside client_module
                    else:
                        current_data = client_output
                        level_processed_here = 1
                        MODULE_EXECUTIONS.labels(tier=MY_TIER, module=module_name).inc()
                        # Metric EEG_DATA_PROCESSED incremented inside client_module
                except Exception as client_exc:
                    print(f"ERROR ({container_name}) during {module_name}: {client_exc}")
                    MODULE_ERRORS.labels(tier=MY_TIER, module=module_name).inc()
                    processing_error = True

            # Level 2: Calculator
            if not processing_error and level_received < 2 and effective_mobile_processing_level >= 2 and concentration_calculator:
                module_name = "calculator"
                if level_processed_here < 1: # Check dependency
                    dep_error_msg = f"Mobile {module_name} (L2) needs L1 input, but only reached L{level_processed_here}."
                    MODULE_ERRORS.labels(tier=MY_TIER, module=module_name).inc()
                    processing_error = True; print(f"ERROR ({container_name}): {dep_error_msg}")
                else:
                    try:
                        with MODULE_LATENCY.labels(tier=MY_TIER, module=module_name).time():
                            calc_output = concentration_calculator.calculate_concentration(current_data)
                        if not calc_output or 'error' in calc_output: raise ValueError(f"{module_name} error: {calc_output.get('error', 'Unknown')}")
                        current_data = calc_output
                        level_processed_here = 2
                        MODULE_EXECUTIONS.labels(tier=MY_TIER, module=module_name).inc()
                    except Exception as calc_exc:
                        print(f"ERROR ({container_name}) during {module_name}: {calc_exc}")
                        MODULE_ERRORS.labels(tier=MY_TIER, module=module_name).inc()
                        processing_error = True

            # Level 3: Connector
            if not processing_error and level_received < 3 and effective_mobile_processing_level >= 3 and connector_module:
                module_name = "connector"
                if level_processed_here < 2: # Check dependency
                    dep_error_msg = f"Mobile {module_name} (L3) needs L2 input, but only reached L{level_processed_here}."
                    MODULE_ERRORS.labels(tier=MY_TIER, module=module_name).inc()
                    processing_error = True; print(f"ERROR ({container_name}): {dep_error_msg}")
                else:
                    try:
                        with MODULE_LATENCY.labels(tier=MY_TIER, module=module_name).time():
                            conn_output = connector_module.process_concentration_data(current_data)
                        if not conn_output or 'error' in conn_output: raise ValueError(f"{module_name} error: {conn_output.get('error', 'Unknown')}")
                        current_data = conn_output
                        level_processed_here = 3
                        MODULE_EXECUTIONS.labels(tier=MY_TIER, module=module_name).inc()
                    except Exception as conn_exc:
                        print(f"ERROR ({container_name}) during {module_name}: {conn_exc}")
                        MODULE_ERRORS.labels(tier=MY_TIER, module=module_name).inc()
                        processing_error = True


            # --- Sending Logic ---
            current_time = time.time()
            if current_time - last_send_attempt_time >= send_interval:
                last_send_attempt_time = current_time
                if not processing_error:
                    # Always send unless processing is fully complete *and* no higher tier exists
                    # (Mobile always has a higher tier - Gateway)
                    if level_processed_here < 3 : # Always true if L3 not run on mobile
                        if gateway_connector.gateway_url:
                            data_to_send = {
                                "payload": current_data,
                                "last_processed_level": level_processed_here # Send the level achieved *here*
                            }
                            print(f"Mobile ({container_name}): Sending data (processed up to L{level_processed_here}) to Gateway...")
                            # Response handling can update local state if needed, e.g., display
                            response_from_upstream = gateway_connector.send_data(data_to_send)
                            if response_from_upstream and client_module:
                                # Example: update display based on final result if it comes back
                                final_level = response_from_upstream.get('final_concentration_level')
                                if final_level: client_module.update_concentration_display(response_from_upstream)
                        else:
                            print(f"WARN ({container_name}): No Gateway URL, cannot send.")
                    else: # level_processed_here == 3
                        print(f"Mobile ({container_name}): Processing finished locally (L3).")
                        if client_module: client_module.update_concentration_display(current_data) # Update display
                        # No send needed if mobile does everything


                elif processing_error: # If there was an error during processing
                    print(f"Mobile ({container_name}): Send skipped due to processing error/discard.")
                    # Optionally send an error status upstream? For now, just skip.

        except KeyboardInterrupt:
            print(f"\nShutting down mobile client ({container_name})...")
            break
        except Exception as e:
            print(f"FATAL Error in mobile main loop ({container_name}): {type(e).__name__} - {str(e)}")
            print(traceback.format_exc())
            time.sleep(5) # Avoid rapid looping on fatal error

        # --- Loop Speed Control ---
        elapsed_time = time.time() - main_loop_start_time
        sleep_time = max(0, send_interval - elapsed_time) # Try to adhere to send_interval
        time.sleep(sleep_time)