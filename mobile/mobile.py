import os, time, uuid, json, socket, threading, traceback
import requests, numpy as np, redis
from flask import Flask
from werkzeug.middleware.dispatcher import DispatcherMiddleware

from shared_modules.client_module import ClientModule
from shared_modules.concentration_calculator_module import ConcentrationCalculatorModule
from shared_modules.connector_module import ConnectorModule
from shared_modules.cpu_monitor import get_container_cpu_percent_non_blocking
from shared_modules.metrics import *

MY_TIER = "mobile"
app = Flask(__name__)
CPU_UTILIZATION = Gauge('cpu_utilization_percent', 'Current CPU utilization percentage', ['container_name'])
container_name = socket.gethostname()

def collect_cpu_metrics():
    while True:
        cpu_info = get_container_cpu_percent_non_blocking()
        if cpu_info:
            normalized_cpu = cpu_info.get('cpu_percent_normalized', float('nan'))
            if not np.isnan(normalized_cpu): CPU_UTILIZATION.labels(container_name=container_name).set(normalized_cpu)
            else: CPU_UTILIZATION.labels(container_name=container_name).set(-1.0)
        else: CPU_UTILIZATION.labels(container_name=container_name).set(-2.0)
        time.sleep(1)

def start_cpu_monitoring():
    cpu_thread = threading.Thread(target=collect_cpu_metrics, daemon=True)
    cpu_thread.start()
    print(f"Mobile ({container_name}): Background CPU monitoring started")

@app.route('/health')
def health_check(): return 'healthy', 200

app.wsgi_app = DispatcherMiddleware(app.wsgi_app, { '/metrics': make_wsgi_app() })

# --- Configuration ---
gateway_name = os.getenv('GATEWAY')
gateway_url = f'http://{gateway_name}:8000/' if gateway_name else None
mobile_processing_level = int(os.getenv('MOBILE_PROCESSING_LEVEL', 1))
effective_mobile_processing_level = max(0, mobile_processing_level)
REDIS_HOST = os.getenv('REDIS_HOST', 'redis')

print(f"--- Mobile Configuration ({container_name}) ---")
print(f"Gateway URL: {gateway_url}")
print(f"Effective Processing Level: {effective_mobile_processing_level}")
print(f"Redis Host: {REDIS_HOST}")
print(f"------------------------------------------")

# --- Gateway Connector (Keep as is from original file) ---
class GatewayConnector:
    def __init__(self, gateway_url, max_retries=3, retry_delay=1):
        self.gateway_url = gateway_url
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.session = requests.Session()
    def send_data(self, data_to_send: dict):
        if not self.gateway_url: return None
        for attempt in range(self.max_retries):
            start_time_gw = time.time()
            try:
                response = self.session.post(self.gateway_url, json=data_to_send, timeout=(5, 10))
                GATEWAY_REQUEST_LATENCY.set(time.time() - start_time_gw)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                print(f"Mobile ({container_name}): Attempt {attempt + 1} to {gateway_name} failed: {type(e).__name__}")
                GATEWAY_REQUEST_FAILURES.inc()
                if attempt < self.max_retries - 1: time.sleep(self.retry_delay)
        return None

# --- Initialize Modules ---
client_module = ClientModule() if effective_mobile_processing_level >= 1 else None
concentration_calculator = ConcentrationCalculatorModule() if effective_mobile_processing_level >= 2 else None
connector_module = ConnectorModule() if effective_mobile_processing_level >= 3 else None
gateway_connector = GatewayConnector(gateway_url)

if __name__ == '__main__':
    start_cpu_monitoring()
    flask_thread = threading.Thread(target=lambda: app.run(host='0.0.0.0', port=9090, debug=False, use_reloader=False), daemon=True)
    flask_thread.start()

    print(f"Connecting to Redis at {REDIS_HOST} to consume from 'eeg_stream'...")
    r = redis.Redis(host=REDIS_HOST, port=6379, db=0)
    p = r.pubsub(ignore_subscribe_messages=True)
    p.subscribe('eeg_stream')

    for message in p.listen():
        try:
            # 1. Receive data from Redis stream
            raw_eeg_data = json.loads(message['data'])
            raw_eeg_data.update({
                "creation_time": time.time(),
                "request_id": str(uuid.uuid4())
            })
            
            # 2. Process the data
            current_data = raw_eeg_data
            level_processed_here = 0
            
            # L1: Client
            if effective_mobile_processing_level >= 1 and client_module:
                with MODULE_LATENCY.labels(tier=MY_TIER, module="client").time():
                    current_data = client_module.process_eeg(current_data)
                if not current_data: continue # Skip if data is invalid/filtered
                level_processed_here = 1
                MODULE_EXECUTIONS.labels(tier=MY_TIER, module="client").inc()
            
            # L2: Calculator
            if effective_mobile_processing_level >= 2 and concentration_calculator:
                with MODULE_LATENCY.labels(tier=MY_TIER, module="calculator").time():
                    current_data = concentration_calculator.calculate_concentration(current_data)
                level_processed_here = 2
                MODULE_EXECUTIONS.labels(tier=MY_TIER, module="calculator").inc()

            # L3: Connector
            if effective_mobile_processing_level >= 3 and connector_module:
                with MODULE_LATENCY.labels(tier=MY_TIER, module="connector").time():
                    current_data = connector_module.process_concentration_data(current_data)
                level_processed_here = 3
                MODULE_EXECUTIONS.labels(tier=MY_TIER, module="connector").inc()

            # 3. Send data upstream if processing is not finished
            if level_processed_here < 3:
                data_to_send = {"payload": current_data, "last_processed_level": level_processed_here}
                gateway_connector.send_data(data_to_send)

        except Exception as e:
            print(f"FATAL Error in mobile main loop: {e}\n{traceback.format_exc()}")
            time.sleep(1)