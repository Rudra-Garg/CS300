import math
import os
import threading
import time
import requests
import json
import traceback
import socket
from flask import Flask, request, jsonify
from werkzeug.middleware.dispatcher import DispatcherMiddleware
import traceback

from shared_modules.client_module import ClientModule
from shared_modules.concentration_calculator_module import ConcentrationCalculatorModule
from shared_modules.connector_module import ConnectorModule

from shared_modules.metrics import *
from shared_modules.cpu_monitor import get_container_cpu_percent_non_blocking

# --- Metrics ---
MY_TIER = "proxy"
# General Metrics (already imported via metrics *)
# MODULE_EXECUTIONS, MODULE_LATENCY, MODULE_ERRORS, PASSTHROUGH_COUNT

# Proxy Specific Metrics
PROXY_REQUEST_COUNT = Counter('proxy_requests_total', 'Total requests received by proxy')
PROXY_INTERNAL_LATENCY = Histogram('proxy_internal_processing_latency_seconds', 'Proxy internal processing latency (excluding upstream wait)')
FORWARD_TO_CLOUD_COUNT = Counter('proxy_forward_to_cloud_total', 'Total requests forwarded to cloud')
FORWARD_TO_CLOUD_LATENCY = Histogram('proxy_forward_to_cloud_latency_seconds', 'Latency for forwarding request to cloud (RTT + cloud processing)')
FORWARD_TO_CLOUD_FAILURES = Counter('proxy_forward_to_cloud_failures_total', 'Failures forwarding to cloud')
PROXY_ERROR_COUNT = Counter('proxy_general_errors_total', 'Total general errors in proxy (outside modules)')
CPU_UTILIZATION = Gauge('cpu_utilization_percent', 'CPU utilization', ['container_name'])
container_name = socket.gethostname()

app = Flask(__name__)

# --- Configuration ---
try:
    proxy_processing_level = int(os.getenv('PROXY_PROCESSING_LEVEL', 3)) # Default higher for proxy
except ValueError:
    print(f"WARN ({container_name}): Invalid PROXY_PROCESSING_LEVEL, defaulting to 3.")
    proxy_processing_level = 3
effective_proxy_processing_level = max(0, proxy_processing_level)

cloud_url = os.getenv('CLOUD_URL') # e.g., http://cloud_py:8000/

print(f"--- Python Proxy Configuration ({container_name}) ---")
print(f"Proxy Processing Level (Config): {proxy_processing_level}")
print(f"Proxy Processing Level (Effective): {effective_proxy_processing_level}")
print(f"Cloud Forward URL: {cloud_url}")
print(f"------------------------------------------")
# ---

# --- Initialize Modules Conditionally ---
client_module = None
concentration_calculator = None
connector_module = None

if effective_proxy_processing_level >= 1 and ClientModule:
    client_module = ClientModule()
    print(f"INFO ({container_name}): Client Module (L1) initialized on Proxy.")
elif effective_proxy_processing_level >= 1: print(f"WARN ({container_name}): L1 requested but module not found.")

if effective_proxy_processing_level >= 2 and ConcentrationCalculatorModule:
    # Check L1 dependency IF L1 is also supposed to run here
    if effective_proxy_processing_level >= 1 and not client_module:
        print(f"WARN ({container_name}): Cannot initialize Calculator (L>=2) if Client (L1) is not also active/found when Proxy level is >= 1. Degrading.")
        effective_proxy_processing_level = 0
    else:
        concentration_calculator = ConcentrationCalculatorModule()
        print(f"INFO ({container_name}): Concentration Calculator Module (L2) initialized on Proxy.")
elif effective_proxy_processing_level >= 2: print(f"WARN ({container_name}): L2 requested but module not found.")

if effective_proxy_processing_level >= 3 and ConnectorModule:
    if concentration_calculator: # Check direct dependency
        connector_module = ConnectorModule()
        print(f"INFO ({container_name}): Connector Module (L3) initialized on Proxy.")
    else:
        print(f"WARN ({container_name}): Cannot initialize Connector (L3) on Proxy without Calculator (L>=2). Degrading level.")
        # Degrade to L2 if calc exists, else L0 if L1 was missing too
        effective_proxy_processing_level = min(effective_proxy_processing_level, 2 if concentration_calculator else 0)
elif effective_proxy_processing_level >= 3: print(f"WARN ({container_name}): L3 requested but module not found.")
# ---

# --- CPU Monitoring (Keep as is) ---
def collect_cpu_metrics():
    while True:
        cpu_info = get_container_cpu_percent_non_blocking()
        if cpu_info:
            normalized_cpu = cpu_info.get('cpu_percent_normalized', math.nan)
            if not math.isnan(normalized_cpu): CPU_UTILIZATION.labels(container_name=container_name).set(normalized_cpu)
            else: CPU_UTILIZATION.labels(container_name=container_name).set(-1.0) # Indicate NaN
        else: CPU_UTILIZATION.labels(container_name=container_name).set(-2.0) # Indicate error getting info
        time.sleep(1)

def start_cpu_monitoring():
    cpu_thread = threading.Thread(target=collect_cpu_metrics, daemon=True)
    cpu_thread.start()
    print(f"Proxy ({container_name}): Background CPU monitoring started")
# ---

# --- Metrics Endpoint ---
app.wsgi_app = DispatcherMiddleware(app.wsgi_app, { '/metrics': make_wsgi_app() })

@app.route('/health')
def health_check():
    return 'healthy', 200

# Renamed endpoint, receives data from the GATEWAY
@app.route('/', methods=['POST'])
def process_gateway_data():
    PROXY_REQUEST_COUNT.inc()
    processing_start_time = time.time()
    level_received = 0
    current_data = None
    level_processed_here = 0 # Track highest level processed *on this proxy*
    processing_error = False
    # The response goes back to the GATEWAY
    final_response_to_gateway = ({"error": "Unknown proxy processing error"}, 500)

    try:
        if not request.is_json: raise TypeError("Request must be JSON")

        incoming_data_full = request.get_json()
        if not incoming_data_full or "payload" not in incoming_data_full or "last_processed_level" not in incoming_data_full:
            raise ValueError("Missing or invalid data structure from gateway")

        level_received = incoming_data_full.get("last_processed_level", 0)
        current_data = incoming_data_full.get("payload")
        level_processed_here = level_received # Start assuming no processing here
        
        request_id = current_data.get("request_id", "unknown") if isinstance(current_data, dict) else "unknown"
        print(f"Proxy ({container_name}, L{effective_proxy_processing_level}): Received data processed up to L{level_received}.")

        # --- Check for Passthrough ---
        if effective_proxy_processing_level == 0 or level_received >= effective_proxy_processing_level:
            print(f"Proxy ({container_name}): Passthrough triggered (Received L{level_received}, Proxy Level {effective_proxy_processing_level})")
            PASSTHROUGH_COUNT.labels(tier=MY_TIER).inc()
        else:
            # --- Processing Pipeline ---

            # Level 1: Client
            if not processing_error and level_received < 1 and effective_proxy_processing_level >= 1 and client_module:
                module_name = "client"
                print(f"Proxy ({container_name}): Running {module_name} (L1)...")
                try:
                    with MODULE_LATENCY.labels(tier=MY_TIER, module=module_name).time():
                        client_output = client_module.process_eeg(current_data)
                    if not client_output:
                        processing_error = True
                        final_response_to_gateway = ({"status": "data_discarded_by_proxy_client", "reason": "quality"}), 400
                    else:
                        current_data = client_output
                        level_processed_here = 1
                        MODULE_EXECUTIONS.labels(tier=MY_TIER, module=module_name).inc()
                except Exception as client_exc:
                    MODULE_ERRORS.labels(tier=MY_TIER, module=module_name).inc()
                    processing_error = True; final_response_to_gateway = ({"status": f"{module_name}_error_on_{MY_TIER}", "detail": str(client_exc)}), 500
                    print(f"ERROR ({container_name}) during {module_name}: {client_exc}")

            # Level 2: Calculator
            if not processing_error and level_received < 2 and effective_proxy_processing_level >= 2 and concentration_calculator:
                module_name = "calculator"
                print(f"Proxy ({container_name}): Running {module_name} (L2)...")
                if level_processed_here < 1: # Check dependency
                    dep_error_msg = f"Proxy {module_name} (L2) needs L1 input, but only reached L{level_processed_here}."
                    MODULE_ERRORS.labels(tier=MY_TIER, module=module_name).inc()
                    processing_error = True; final_response_to_gateway = ({"status":"dependency_error", "detail": dep_error_msg}), 500
                    print(f"ERROR ({container_name}): {dep_error_msg}")
                else:
                    try:
                        with MODULE_LATENCY.labels(tier=MY_TIER, module=module_name).time():
                            calc_output = concentration_calculator.calculate_concentration(current_data)
                        if not calc_output or 'error' in calc_output: raise ValueError(f"{module_name} error: {calc_output.get('error', 'Unknown')}")
                        current_data = calc_output
                        level_processed_here = 2
                        MODULE_EXECUTIONS.labels(tier=MY_TIER, module=module_name).inc()
                    except Exception as calc_exc:
                        MODULE_ERRORS.labels(tier=MY_TIER, module=module_name).inc()
                        processing_error = True; final_response_to_gateway = ({"status": f"{module_name}_error_on_{MY_TIER}", "detail": str(calc_exc)}), 500
                        print(f"ERROR ({container_name}) during {module_name}: {calc_exc}")

            # Level 3: Connector
            if not processing_error and level_received < 3 and effective_proxy_processing_level >= 3 and connector_module:
                module_name = "connector"
                print(f"Proxy ({container_name}): Running {module_name} (L3)...")
                if level_processed_here < 2: # Check dependency
                    dep_error_msg = f"Proxy {module_name} (L3) needs L2 input, but only reached L{level_processed_here}."
                    MODULE_ERRORS.labels(tier=MY_TIER, module=module_name).inc()
                    processing_error = True; final_response_to_gateway = ({"status":"dependency_error", "detail": dep_error_msg}), 500
                    print(f"ERROR ({container_name}): {dep_error_msg}")
                else:
                    try:
                        with MODULE_LATENCY.labels(tier=MY_TIER, module=module_name).time():
                            conn_output = connector_module.process_concentration_data(current_data)
                        # --- CALCULATE AND RECORD E2E LATENCY ---
                        if conn_output and 'error' not in conn_output:
                            creation_time = current_data.get('creation_time') # Get from data BEFORE overwriting
                            if creation_time:
                                e2e_latency = time.time() - creation_time
                                E2E_LATENCY.labels(final_tier=MY_TIER).observe(e2e_latency)
                                print(f"Gateway ({container_name}) ReqID:{request_id[-6:]}: L3 Complete. E2E Latency: {e2e_latency:.4f}s")
                            else:
                                print(f"WARN ({container_name}) ReqID:{request_id[-6:]}: Missing creation_time for E2E latency calc.")
                        # ---------------------------------------

                        
                        if not conn_output or 'error' in conn_output: raise ValueError(f"{module_name} error: {conn_output.get('error', 'Unknown')}")
                        current_data = conn_output
                        level_processed_here = 3
                        MODULE_EXECUTIONS.labels(tier=MY_TIER, module=module_name).inc()
                    except Exception as conn_exc:
                        MODULE_ERRORS.labels(tier=MY_TIER, module=module_name).inc()
                        processing_error = True; final_response_to_gateway = ({"status": f"{module_name}_error_on_{MY_TIER}", "detail": str(conn_exc)}), 500
                        print(f"ERROR ({container_name}) during {module_name}: {conn_exc}")


        # Record internal processing time
        internal_processing_duration = time.time() - processing_start_time
        PROXY_INTERNAL_LATENCY.observe(internal_processing_duration)

        # --- Forwarding Decision ---
        if not processing_error:
            if level_processed_here < 3: # Need to forward UPWARDS to Cloud
                if cloud_url:
                    data_to_forward = {"payload": current_data, "last_processed_level": level_processed_here}
                    print(f"Proxy ({container_name}): Forwarding data (processed up to L{level_processed_here}) to Cloud ({cloud_url})...")
                    forward_start_time = time.time()
                    try:
                        cloud_response = requests.post(cloud_url, json=data_to_forward, timeout=(10, 20)) # Longer timeout for cloud
                        forward_duration = time.time() - forward_start_time
                        FORWARD_TO_CLOUD_LATENCY.observe(forward_duration) # RTT + Cloud time
                        cloud_response.raise_for_status()
                        FORWARD_TO_CLOUD_COUNT.inc()
                        print(f"Proxy ({container_name}): Forward success to Cloud. RTT+CloudTime: {forward_duration:.4f}s")
                        # Relay cloud's response back to the gateway
                        try:
                            response_payload = cloud_response.json()
                            response_payload['processed_up_to'] = response_payload.get('processed_up_to', level_processed_here)
                            final_response_to_gateway = (response_payload, cloud_response.status_code)
                        except json.JSONDecodeError:
                            final_response_to_gateway = ({"status": f"cloud_status_{cloud_response.status_code}_no_json", "processed_up_to": level_processed_here}), cloud_response.status_code
                    except requests.exceptions.RequestException as e:
                        FORWARD_TO_CLOUD_FAILURES.inc()
                        error_detail = f"{type(e).__name__}: {e}"
                        print(f"ERROR ({container_name}): Failed to forward to Cloud: {error_detail}")
                        final_response_to_gateway = ({"status": "forward_to_cloud_failed", "processed_up_to": level_processed_here, "detail": error_detail}), 502
                else: # Cannot forward
                    print(f"WARN ({container_name}): CLOUD_URL not set, cannot forward incomplete processing (L{level_processed_here}).")
                    final_response_to_gateway = ({"status": f"processed_L{level_processed_here}_cannot_forward_no_cloud"}), 500
            else: # level_processed_here == 3 (Final processing done here on Proxy)
                print(f"Proxy ({container_name}): Final processing complete (L3).")
                # Structure the response for the gateway
                final_response_to_gateway = ({"status": "processing_complete", "final_payload_preview": json.dumps(current_data)[:100], "processed_up_to": 3}), 200

        # Return the determined response and status code TO THE GATEWAY
        return jsonify(final_response_to_gateway[0]), final_response_to_gateway[1]

    except (TypeError, ValueError) as req_err: # Catch specific request format errors
        PROXY_ERROR_COUNT.inc()
        print(f"ERROR ({container_name}): Invalid request data from gateway: {req_err}")
        return jsonify({"error": f"Bad Request from Gateway: {req_err}"}), 400
    except Exception as e: # Catch all other unexpected errors
        PROXY_ERROR_COUNT.inc()
        internal_processing_duration = time.time() - processing_start_time
        PROXY_INTERNAL_LATENCY.observe(internal_processing_duration)
        print(f"FATAL Error in Proxy ({container_name}): {type(e).__name__} - {e}")
        print(traceback.format_exc())
        # Return generic error to gateway
        return jsonify({"error": "Internal server error on proxy"}), 500

if __name__ == '__main__':
    print("Python Proxy Service Starting...")
    start_cpu_monitoring()
    app.run(host='0.0.0.0', port=8000)