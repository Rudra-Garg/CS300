import math
import os
import threading
import time
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
from shared_modules.cpu_monitor import get_container_cpu_percent_non_blocking # Optional for cloud

# --- Metrics ---
MY_TIER = "cloud"
# General Metrics (already imported via metrics *)
# MODULE_EXECUTIONS, MODULE_LATENCY, MODULE_ERRORS, PASSTHROUGH_COUNT (Passthrough N/A here)

# Cloud Specific Metrics
CLOUD_REQUEST_COUNT = Counter('cloud_requests_total', 'Total requests received by cloud')
CLOUD_INTERNAL_LATENCY = Histogram('cloud_internal_processing_latency_seconds', 'Cloud internal processing latency')
CLOUD_ERROR_COUNT = Counter('cloud_general_errors_total', 'Total general errors in cloud (outside modules)')
CPU_UTILIZATION = Gauge('cpu_utilization_percent', 'CPU utilization', ['container_name']) # Optional
container_name = socket.gethostname()

app = Flask(__name__)

# --- Configuration ---
try:
    cloud_processing_level = int(os.getenv('CLOUD_PROCESSING_LEVEL', 3)) # Cloud defaults to capable of all
except ValueError:
    print(f"WARN ({container_name}): Invalid CLOUD_PROCESSING_LEVEL, defaulting to 3.")
    cloud_processing_level = 3
# Effective level is less critical here as it's the end, but keep for consistency
effective_cloud_processing_level = max(0, cloud_processing_level)

print(f"--- Python Cloud Configuration ({container_name}) ---")
print(f"Cloud Processing Level (Config): {cloud_processing_level}")
print(f"Cloud Processing Level (Effective): {effective_cloud_processing_level}")
print(f"------------------------------------------")
# ---

# --- Initialize Modules Conditionally ---
# Cloud *can* run anything if configured and modules available
client_module = None
concentration_calculator = None
connector_module = None

if effective_cloud_processing_level >= 1 and ClientModule:
    client_module = ClientModule()
    print(f"INFO ({container_name}): Client Module (L1) initialized on Cloud.")
elif effective_cloud_processing_level >= 1: print(f"WARN ({container_name}): L1 requested but module not found.")

if effective_cloud_processing_level >= 2 and ConcentrationCalculatorModule:
    # Dependency check (only relevant if L1 was *supposed* to run here but didn't init)
    if effective_cloud_processing_level >= 1 and not client_module:
        print(f"WARN ({container_name}): Cannot initialize Calculator (L>=2) if Client (L1) is not also active/found when Cloud level is >= 1. Degrading.")
        effective_cloud_processing_level = 0
    else:
        concentration_calculator = ConcentrationCalculatorModule()
        print(f"INFO ({container_name}): Concentration Calculator Module (L2) initialized on Cloud.")
elif effective_cloud_processing_level >= 2: print(f"WARN ({container_name}): L2 requested but module not found.")

if effective_cloud_processing_level >= 3 and ConnectorModule:
    if concentration_calculator: # Check direct dependency
        connector_module = ConnectorModule()
        print(f"INFO ({container_name}): Connector Module (L3) initialized on Cloud.")
    else:
        print(f"WARN ({container_name}): Cannot initialize Connector (L3) on Cloud without Calculator (L>=2). Degrading level.")
        effective_cloud_processing_level = min(effective_cloud_processing_level, 2 if concentration_calculator else 0)
elif effective_cloud_processing_level >= 3: print(f"WARN ({container_name}): L3 requested but module not found.")
# ---

# --- CPU Monitoring (Optional for Cloud) ---
def collect_cpu_metrics():
    while True:
        cpu_info = get_container_cpu_percent_non_blocking()
        if cpu_info:
            normalized_cpu = cpu_info.get('cpu_percent_normalized', math.nan) # Cloud might not have quota
            raw_cpu = cpu_info.get('cpu_percent_raw', math.nan)
            # Report raw if normalized isn't available
            display_cpu = normalized_cpu if not math.isnan(normalized_cpu) else raw_cpu
            if not math.isnan(display_cpu): CPU_UTILIZATION.labels(container_name=container_name).set(display_cpu)
            else: CPU_UTILIZATION.labels(container_name=container_name).set(-1.0) # Indicate NaN
        else: CPU_UTILIZATION.labels(container_name=container_name).set(-2.0) # Indicate error
        time.sleep(5) # Cloud monitoring can be less frequent

def start_cpu_monitoring():
    cpu_thread = threading.Thread(target=collect_cpu_metrics, daemon=True)
    cpu_thread.start()
    print(f"Cloud ({container_name}): Background CPU monitoring started (optional)")
# ---

# --- Metrics Endpoint ---
app.wsgi_app = DispatcherMiddleware(app.wsgi_app, { '/metrics': make_wsgi_app() })

@app.route('/health')
def health_check():
    return 'healthy', 200

# Renamed endpoint, receives data from the PROXY
@app.route('/', methods=['POST'])
def process_proxy_data():
    CLOUD_REQUEST_COUNT.inc()
    processing_start_time = time.time()
    level_received = 0
    current_data = None
    level_processed_here = 0 # Track highest level processed *on the cloud*
    processing_error = False
    # The response goes back to the PROXY
    final_response_to_proxy = ({"error": "Unknown cloud processing error"}, 500)

    try:
        if not request.is_json: raise TypeError("Request must be JSON")

        incoming_data_full = request.get_json()
        if not incoming_data_full or "payload" not in incoming_data_full or "last_processed_level" not in incoming_data_full:
            raise ValueError("Missing or invalid data structure from proxy")

        level_received = incoming_data_full.get("last_processed_level", 0)
        current_data = incoming_data_full.get("payload")
        level_processed_here = level_received # Start assuming no processing
        
        request_id = current_data.get("request_id", "unknown") if isinstance(current_data, dict) else "unknown"
        print(f"Cloud ({container_name}, L{effective_cloud_processing_level}): Received data processed up to L{level_received}.")

        # Cloud is the end, no passthrough. Process everything possible up to its level.

        # --- Processing Pipeline ---

        # Level 1: Client
        if not processing_error and level_received < 1 and effective_cloud_processing_level >= 1 and client_module:
            module_name = "client"
            print(f"Cloud ({container_name}): Running {module_name} (L1)...")
            try:
                with MODULE_LATENCY.labels(tier=MY_TIER, module=module_name).time():
                    client_output = client_module.process_eeg(current_data)
                if not client_output:
                    processing_error = True
                    final_response_to_proxy = ({"status": "data_discarded_by_cloud_client", "reason": "quality"}), 400
                else:
                    current_data = client_output
                    level_processed_here = 1
                    MODULE_EXECUTIONS.labels(tier=MY_TIER, module=module_name).inc()
            except Exception as client_exc:
                MODULE_ERRORS.labels(tier=MY_TIER, module=module_name).inc()
                processing_error = True; final_response_to_proxy = ({"status": f"{module_name}_error_on_{MY_TIER}", "detail": str(client_exc)}), 500
                print(f"ERROR ({container_name}) during {module_name}: {client_exc}")

        # Level 2: Calculator
        if not processing_error and level_received < 2 and effective_cloud_processing_level >= 2 and concentration_calculator:
            module_name = "calculator"
            print(f"Cloud ({container_name}): Running {module_name} (L2)...")
            if level_processed_here < 1: # Check dependency
                dep_error_msg = f"Cloud {module_name} (L2) needs L1 input, but only reached L{level_processed_here}."
                MODULE_ERRORS.labels(tier=MY_TIER, module=module_name).inc()
                processing_error = True; final_response_to_proxy = ({"status":"dependency_error", "detail": dep_error_msg}), 500
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
                    processing_error = True; final_response_to_proxy = ({"status": f"{module_name}_error_on_{MY_TIER}", "detail": str(calc_exc)}), 500
                    print(f"ERROR ({container_name}) during {module_name}: {calc_exc}")

        # Level 3: Connector
        if not processing_error and level_received < 3 and effective_cloud_processing_level >= 3 and connector_module:
            module_name = "connector"
            print(f"Cloud ({container_name}): Running {module_name} (L3)...")
            if level_processed_here < 2: # Check dependency
                dep_error_msg = f"Cloud {module_name} (L3) needs L2 input, but only reached L{level_processed_here}."
                MODULE_ERRORS.labels(tier=MY_TIER, module=module_name).inc()
                processing_error = True; final_response_to_proxy = ({"status":"dependency_error", "detail": dep_error_msg}), 500
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
                    processing_error = True; final_response_to_proxy = ({"status": f"{module_name}_error_on_{MY_TIER}", "detail": str(conn_exc)}), 500
                    print(f"ERROR ({container_name}) during {module_name}: {conn_exc}")


        # Record internal processing time
        internal_processing_duration = time.time() - processing_start_time
        CLOUD_INTERNAL_LATENCY.observe(internal_processing_duration)

        # --- Final Response ---
        # Cloud is the end point, so it always returns the result (or error)
        if not processing_error:
            print(f"Cloud ({container_name}): Final processing complete (up to L{level_processed_here}).")
            # Structure the final response for the proxy
            final_response_to_proxy = ({"status": "processing_complete", "final_payload_preview": json.dumps(current_data)[:100], "processed_up_to": level_processed_here}), 200
        # else: final_response_to_proxy is already set in the except blocks

        # Return the determined response and status code TO THE PROXY
        return jsonify(final_response_to_proxy[0]), final_response_to_proxy[1]

    except (TypeError, ValueError) as req_err: # Catch specific request format errors
        CLOUD_ERROR_COUNT.inc()
        print(f"ERROR ({container_name}): Invalid request data from proxy: {req_err}")
        return jsonify({"error": f"Bad Request from Proxy: {req_err}"}), 400
    except Exception as e: # Catch all other unexpected errors
        CLOUD_ERROR_COUNT.inc()
        internal_processing_duration = time.time() - processing_start_time
        CLOUD_INTERNAL_LATENCY.observe(internal_processing_duration)
        print(f"FATAL Error in Cloud ({container_name}): {type(e).__name__} - {e}")
        print(traceback.format_exc())
        # Return generic error to proxy
        return jsonify({"error": "Internal server error on cloud"}), 500

if __name__ == '__main__':
    print("Python Cloud Service Starting...")
    start_cpu_monitoring() # Optional CPU monitoring
    app.run(host='0.0.0.0', port=8000)