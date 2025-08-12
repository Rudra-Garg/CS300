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
MY_TIER = "gateway"
# General Metrics (already imported via metrics *)
# MODULE_EXECUTIONS, MODULE_LATENCY, MODULE_ERRORS, PASSTHROUGH_COUNT

# Gateway Specific Metrics
REQUEST_COUNT = Counter('gateway_requests_total', 'Total number of requests received by gateway')
REQUEST_LATENCY = Histogram('gateway_internal_processing_latency_seconds', 'Gateway internal processing latency (excluding upstream wait)')
FORWARD_TO_PROXY_COUNT = Counter('gateway_forward_to_proxy_total', 'Total requests forwarded to proxy')
FORWARD_TO_PROXY_LATENCY = Histogram('gateway_forward_to_proxy_latency_seconds', 'Latency for forwarding request to proxy (network RTT + proxy processing)')
FORWARD_TO_PROXY_FAILURES = Counter('gateway_forward_to_proxy_failures_total', 'Failures forwarding to proxy')
ERROR_COUNT = Counter('gateway_general_errors_total', 'Total general processing errors on gateway (outside modules)') # Renamed for clarity
CPU_UTILIZATION = Gauge('cpu_utilization_percent', 'Current CPU utilization percentage', ['container_name'])
container_name = socket.gethostname()

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
    print(f"Gateway ({container_name}): Background CPU monitoring started")
# ---

app = Flask(__name__)

# --- Configuration ---
proxy_url = os.getenv('PROXY_URL') # e.g., http://proxy_py:8000/process
try:
    gateway_processing_level = int(os.getenv('GATEWAY_PROCESSING_LEVEL', 2))
except ValueError:
    print(f"WARN ({container_name}): Invalid GATEWAY_PROCESSING_LEVEL, defaulting to 2.")
    gateway_processing_level = 2
effective_gateway_processing_level = max(0, gateway_processing_level)

print(f"--- Gateway Configuration ({container_name}) ---")
print(f"Proxy URL: {proxy_url}")
print(f"Gateway Processing Level (Config): {gateway_processing_level}")
print(f"Gateway Processing Level (Effective): {effective_gateway_processing_level}")
print(f"--------------------------------------")
# ---

# --- Initialize Modules Conditionally ---
client_module = None
concentration_calculator = None
connector_module = None

if effective_gateway_processing_level >= 1 and ClientModule:
    client_module = ClientModule()
    print(f"INFO ({container_name}): Client Module (L1) initialized on Gateway.")
elif effective_gateway_processing_level >= 1: print(f"WARN ({container_name}): L1 requested but module not found.")

if effective_gateway_processing_level >= 2 and ConcentrationCalculatorModule:
    # Check L1 dependency IF L1 is also supposed to run here
    if effective_gateway_processing_level >= 1 and not client_module:
        print(f"WARN ({container_name}): Cannot initialize Calculator (L>=2) if Client (L1) is not also active/found when Gateway level is >= 1. Degrading.")
        effective_gateway_processing_level = 0 # Degrade if L1 is missing but needed implicitly
    else:
        concentration_calculator = ConcentrationCalculatorModule()
        print(f"INFO ({container_name}): Concentration Calculator Module (L2) initialized on Gateway.")
elif effective_gateway_processing_level >= 2: print(f"WARN ({container_name}): L2 requested but module not found.")


if effective_gateway_processing_level >= 3 and ConnectorModule:
    if concentration_calculator: # Check direct dependency
        connector_module = ConnectorModule()
        print(f"INFO ({container_name}): Connector Module (L3) initialized on Gateway.")
    else:
        print(f"WARN ({container_name}): Cannot initialize Connector (L3) on Gateway without Calculator (L>=2). Degrading level.")
        effective_gateway_processing_level = min(effective_gateway_processing_level, 2 if concentration_calculator else 0) # Degrade
elif effective_gateway_processing_level >= 3: print(f"WARN ({container_name}): L3 requested but module not found.")
# ---

app.wsgi_app = DispatcherMiddleware(app.wsgi_app, { '/metrics': make_wsgi_app() })

@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy'}), 200

# Renamed endpoint for clarity, receives data from MOBILE
@app.route('/', methods=['POST'])
def process_mobile_data():
    REQUEST_COUNT.inc()
    processing_start_time = time.time()
    level_received = 0
    current_data = None
    level_processed_here = 0 # Track highest level processed *on this gateway*
    processing_error = False
    final_response_to_mobile = ({"error": "Unknown gateway processing error"}, 500)

    try:
        if not request.is_json: raise TypeError("Request must be JSON")

        incoming_data_full = request.get_json()
        if not incoming_data_full or "payload" not in incoming_data_full or "last_processed_level" not in incoming_data_full:
            raise ValueError("Missing or invalid data structure from mobile")

        level_received = incoming_data_full.get("last_processed_level", 0)
        current_data = incoming_data_full.get("payload")
        level_processed_here = level_received # Start assuming no processing happens here
        request_id = current_data.get("request_id", "unknown") if isinstance(current_data, dict) else "unknown"
        print(f"Gateway ({container_name}, L{effective_gateway_processing_level}): Received data processed up to L{level_received}.")

        # --- Check for Passthrough First ---
        if effective_gateway_processing_level == 0 or level_received >= effective_gateway_processing_level:
            print(f"Gateway ({container_name}): Passthrough triggered (Received L{level_received}, Gateway Level {effective_gateway_processing_level})")
            PASSTHROUGH_COUNT.labels(tier=MY_TIER).inc()
            # Skip processing modules, data remains as received
            # level_processed_here remains level_received
        else:
            # --- Processing Pipeline (Only if not passthrough) ---

            # Level 1: Client
            if not processing_error and level_received < 1 and effective_gateway_processing_level >= 1 and client_module:
                module_name = "client"
                print(f"Gateway ({container_name}): Running {module_name} (L1)...")
                try:
                    with MODULE_LATENCY.labels(tier=MY_TIER, module=module_name).time():
                        client_output = client_module.process_eeg(current_data)
                    if not client_output:
                        processing_error = True # Stop processing
                        # Metric EEG_DISCARDED_TOTAL incremented inside client_module
                        final_response_to_mobile = ({"status": "data_discarded_by_gateway_client", "reason": "quality"}), 400 # Inform mobile
                    else:
                        current_data = client_output
                        level_processed_here = 1
                        MODULE_EXECUTIONS.labels(tier=MY_TIER, module=module_name).inc()
                        # Metric EEG_DATA_PROCESSED incremented inside client_module
                except Exception as client_exc:
                    MODULE_ERRORS.labels(tier=MY_TIER, module=module_name).inc()
                    processing_error = True; final_response_to_mobile = ({"status": f"{module_name}_error_on_{MY_TIER}", "detail": str(client_exc)}), 500
                    print(f"ERROR ({container_name}) during {module_name}: {client_exc}")

            # Level 2: Calculator
            if not processing_error and level_received < 2 and effective_gateway_processing_level >= 2 and concentration_calculator:
                module_name = "calculator"
                print(f"Gateway ({container_name}): Running {module_name} (L2)...")
                if level_processed_here < 1: # Check dependency
                    dep_error_msg = f"Gateway {module_name} (L2) needs L1 input, but only reached L{level_processed_here}."
                    MODULE_ERRORS.labels(tier=MY_TIER, module=module_name).inc()
                    processing_error = True; final_response_to_mobile = ({"status":"dependency_error", "detail": dep_error_msg}), 500
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
                        processing_error = True; final_response_to_mobile = ({"status": f"{module_name}_error_on_{MY_TIER}", "detail": str(calc_exc)}), 500
                        print(f"ERROR ({container_name}) during {module_name}: {calc_exc}")


            # Level 3: Connector
            if not processing_error and level_received < 3 and effective_gateway_processing_level >= 3 and connector_module:
                module_name = "connector"
                print(f"Gateway ({container_name}): Running {module_name} (L3)...")
                if level_processed_here < 2: # Check dependency
                    dep_error_msg = f"Gateway {module_name} (L3) needs L2 input, but only reached L{level_processed_here}."
                    MODULE_ERRORS.labels(tier=MY_TIER, module=module_name).inc()
                    processing_error = True; final_response_to_mobile = ({"status":"dependency_error", "detail": dep_error_msg}), 500
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
                        processing_error = True; final_response_to_mobile = ({"status": f"{module_name}_error_on_{MY_TIER}", "detail": str(conn_exc)}), 500
                        print(f"ERROR ({container_name}) during {module_name}: {conn_exc}")


        # Record internal processing time (might be ~0 for passthrough)
        internal_processing_duration = time.time() - processing_start_time
        REQUEST_LATENCY.observe(internal_processing_duration)

        # --- Forwarding Decision ---
        if not processing_error:
            if level_processed_here < 3: # Need to forward UPWARDS
                if proxy_url:
                    data_to_forward = {"payload": current_data, "last_processed_level": level_processed_here}
                    print(f"Gateway ({container_name}): Forwarding data (processed up to L{level_processed_here}) to Proxy ({proxy_url})...")
                    forward_start_time = time.time()
                    try:
                        proxy_response = requests.post(proxy_url, json=data_to_forward, timeout=(5, 10)) # connect, read
                        forward_duration = time.time() - forward_start_time
                        FORWARD_TO_PROXY_LATENCY.observe(forward_duration) # Observe RTT + Proxy time
                        proxy_response.raise_for_status()
                        FORWARD_TO_PROXY_COUNT.inc()
                        print(f"Gateway ({container_name}): Forward success to Proxy. RTT+ProxyTime: {forward_duration:.4f}s")
                        # --- IMPORTANT: Relay proxy's response back to mobile ---
                        try:
                            # Add the level processed *here* for mobile's info
                            response_payload = proxy_response.json()
                            response_payload['processed_up_to'] = response_payload.get('processed_up_to', level_processed_here) # Pass highest level seen
                            final_response_to_mobile = (response_payload, proxy_response.status_code)
                        except json.JSONDecodeError:
                            final_response_to_mobile = ({"status": f"proxy_status_{proxy_response.status_code}_no_json", "processed_up_to": level_processed_here}), proxy_response.status_code
                    except requests.exceptions.RequestException as e:
                        FORWARD_TO_PROXY_FAILURES.inc()
                        error_detail = f"{type(e).__name__}: {e}"
                        print(f"ERROR ({container_name}): Failed to forward to Proxy: {error_detail}")
                        final_response_to_mobile = ({"status": "forward_to_proxy_failed", "processed_up_to": level_processed_here, "detail": error_detail}), 502
                else: # Cannot forward
                    print(f"WARN ({container_name}): PROXY_URL not set, cannot forward incomplete processing (L{level_processed_here}).")
                    final_response_to_mobile = ({"status": f"processed_L{level_processed_here}_cannot_forward_no_proxy"}), 500
            else: # level_processed_here == 3 (Final processing done here on Gateway)
                print(f"Gateway ({container_name}): Final processing complete (L3).")
                # Structure the response for mobile
                final_response_to_mobile = ({"status": "processing_complete", "final_payload_preview": json.dumps(current_data)[:100], "processed_up_to": 3}), 200

        # Return the determined response and status code TO THE MOBILE
        return jsonify(final_response_to_mobile[0]), final_response_to_mobile[1]

    except (TypeError, ValueError) as req_err: # Catch specific request format errors
        ERROR_COUNT.inc()
        print(f"ERROR ({container_name}): Invalid request data: {req_err}")
        return jsonify({"error": f"Bad Request: {req_err}"}), 400
    except Exception as e: # Catch all other unexpected errors
        ERROR_COUNT.inc()
        # Still record latency if possible
        internal_processing_duration = time.time() - processing_start_time
        REQUEST_LATENCY.observe(internal_processing_duration)
        print(f"FATAL Error in Gateway ({container_name}): {type(e).__name__} - {e}")
        print(traceback.format_exc())
        # Return generic error to mobile
        return jsonify({"error": "Internal server error on gateway"}), 500

if __name__ == '__main__':
    start_cpu_monitoring()
    app.run(host='0.0.0.0', port=8000)