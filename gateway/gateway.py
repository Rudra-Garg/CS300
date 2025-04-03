import math
import os
import time
import requests
import json
import traceback
import psutil
import socket
from flask import Flask, request, jsonify
from prometheus_client import Counter, Histogram, start_http_server, make_wsgi_app, Gauge
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from shared_modules.concentration_calculator_module import ConcentrationCalculatorModule
from shared_modules.cpu_monitor import get_container_cpu_percent_non_blocking


# --- Metrics (Add Forwarding Metrics) ---
REQUEST_COUNT = Counter('gateway_requests_total', 'Total number of requests processed')
REQUEST_LATENCY = Histogram('gateway_request_duration_seconds', 'Request processing latency (Calc only)') # Renamed for clarity
FORWARD_TO_PROXY_COUNT = Counter('gateway_forward_to_proxy_total', 'Total requests forwarded to proxy')
FORWARD_TO_PROXY_LATENCY = Histogram('gateway_forward_to_proxy_latency_seconds', 'Latency for forwarding request to proxy')
FORWARD_TO_PROXY_FAILURES = Counter('gateway_forward_to_proxy_failures_total', 'Failures forwarding to proxy')
ERROR_COUNT = Counter('gateway_errors_total', 'Total number of processing errors')
CPU_UTILIZATION = Gauge('cpu_utilization_percent', 'Current CPU utilization percentage', ['container_name'])
container_name = socket.gethostname()


app = Flask(__name__)

# --- Configuration ---
proxy_url = os.getenv('PROXY_URL') # e.g., http://proxy_py:8000/process
if not proxy_url:
    print("FATAL: PROXY_URL environment variable not set!")
    # Decide how to handle this - exit or run degraded? For now, print error.
print(f"Gateway configured to forward results to: {proxy_url}")
# ---

concentration_calculator = ConcentrationCalculatorModule()

# Add metrics endpoint
app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {
    '/metrics': make_wsgi_app()
})

@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy'}), 200

@app.route('/', methods=['POST'])
def process_and_forward():
    
    # --- CPU Monitoring ---
    cpu_info = get_container_cpu_percent_non_blocking()
    if cpu_info:
        normalized_cpu = cpu_info.get('cpu_percent_normalized', math.nan)
        if not math.isnan(normalized_cpu):
            CPU_UTILIZATION.labels(container_name=container_name).set(normalized_cpu)
            # print(f"DEBUG Gateway CPU Norm: {normalized_cpu:.1f}%")
        else:
            CPU_UTILIZATION.labels(container_name=container_name).set(-1.0)
    else:
        CPU_UTILIZATION.labels(container_name=container_name).set(-2.0)
    # --- End CPU Monitoring ---
    
    REQUEST_COUNT.inc()
    calc_start_time = time.time()
    calc_result = None
    forward_status = "not_attempted"

    try:
        if not request.is_json: # ... (validation) ...
             ERROR_COUNT.inc(); return jsonify({"error": "Request must be JSON"}), 415
        client_output_data = request.get_json().get("eeg_data")
        if not client_output_data: # ... (validation) ...
            ERROR_COUNT.inc(); return jsonify({"error": "Missing 'eeg_data'"}), 400

        # 1. Run Concentration Calculator
        print("Gateway: Received data, running Calculator...")
        calc_result = concentration_calculator.calculate_concentration(client_output_data)
        calc_duration = time.time() - calc_start_time
        REQUEST_LATENCY.observe(calc_duration) # Observe calculator latency
        print(f"Gateway: Calculator finished in {calc_duration:.4f}s.")

        if not calc_result or 'error' in calc_result:
            error_msg = f"Concentration calculation failed on gateway: {calc_result}"
            print(f"ERROR: {error_msg}")
            ERROR_COUNT.inc()
            # Still return 202 to mobile, but indicate failure upstream
            return jsonify({"status": "calc_error_not_forwarded", "detail": error_msg}), 202

        # 2. Forward Result to Proxy (if calculation succeeded)
        if proxy_url:
            print(f"Gateway: Forwarding result to Proxy ({proxy_url})...")
            forward_start_time = time.time()
            try:
                # Proxy expects the result of the calculator
                proxy_response = requests.post(proxy_url, json=calc_result, timeout=(5, 10))
                proxy_response.raise_for_status() # Check for HTTP errors from proxy

                forward_duration = time.time() - forward_start_time
                FORWARD_TO_PROXY_LATENCY.observe(forward_duration)
                FORWARD_TO_PROXY_COUNT.inc()
                forward_status = "success"
                print(f"Gateway: Successfully forwarded to Proxy in {forward_duration:.4f}s (Proxy Status: {proxy_response.status_code})")

            except requests.exceptions.RequestException as e:
                forward_duration = time.time() - forward_start_time # Observe latency even on failure
                FORWARD_TO_PROXY_LATENCY.observe(forward_duration)
                FORWARD_TO_PROXY_FAILURES.inc()
                forward_status = "failed"
                print(f"ERROR: Failed to forward to Proxy: {type(e).__name__} - {e}")
                # Log the error but still return 202 to mobile, indicating forward failure
            except Exception as e_inner:
                 FORWARD_TO_PROXY_FAILURES.inc()
                 forward_status = "failed_unexpected"
                 print(f"ERROR: Unexpected error during proxy forward: {type(e_inner).__name__} - {e_inner}")

        else:
            print("WARN: PROXY_URL not set, cannot forward result.")
            forward_status = "skipped_no_url"

        # 3. Send Acknowledgement back to Mobile
        # Indicate success/failure of forwarding step
        return jsonify({"status": f"forwarded_to_proxy_{forward_status}"}), 202 # Accepted

    except Exception as e:
        # Catch errors during request handling or calculation before forwarding
        ERROR_COUNT.inc()
        calc_duration = time.time() - calc_start_time # Observe latency up to the error point
        REQUEST_LATENCY.observe(calc_duration)
        print(f"FATAL Error processing request in Gateway: {type(e).__name__} - {e}")
        print(traceback.format_exc())
        # Return 500 to mobile indicating gateway failure before forwarding
        return jsonify({"error": "Internal server error on gateway"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
