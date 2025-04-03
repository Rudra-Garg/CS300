import os
import time
import json
import traceback
import psutil
import math
import socket
from flask import Flask, request, jsonify
from prometheus_client import Counter, Histogram, start_http_server, make_wsgi_app, Gauge
from werkzeug.middleware.dispatcher import DispatcherMiddleware

from shared_modules.connector_module import ConnectorModule
from shared_modules.concentration_calculator_module import ConcentrationCalculatorModule 
from shared_modules.cpu_monitor import get_container_cpu_percent_non_blocking


# --- Metrics ---
PROXY_REQUEST_COUNT = Counter('proxy_requests_total', 'Total requests received by proxy')
PROXY_CONNECTOR_LATENCY = Histogram('proxy_connector_latency_seconds', 'Latency of connector processing')
PROXY_ERROR_COUNT = Counter('proxy_errors_total', 'Total processing errors in proxy')
CPU_UTILIZATION = Gauge('cpu_utilization_percent', 'Current CPU utilization percentage', ['container_name'])
container_name = socket.gethostname()

app = Flask(__name__)



# --- Instantiate Modules ---
connector_module = ConnectorModule()
# ---

# --- Metrics Endpoint ---
app.wsgi_app = DispatcherMiddleware(app.wsgi_app, { '/metrics': make_wsgi_app() })
# ---

# Add health check endpoint
@app.route('/health')
def health_check():
    return 'healthy', 200

# This endpoint receives the *result* from the gateway's calculator
@app.route('/process', methods=['POST'])
def process_calculator_result():
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
    
    PROXY_REQUEST_COUNT.inc()
    connector_start_time = time.time()
    final_result = None

    try:
        if not request.is_json:
            PROXY_ERROR_COUNT.inc()
            return jsonify({"error": "Request must be JSON"}), 415

        calculator_result = request.get_json()
        if not calculator_result:
            PROXY_ERROR_COUNT.inc()
            return jsonify({"error": "Missing calculator result data"}), 400

        # --- Run Connector Module ---
        print("Proxy: Received calculator result, running Connector...")
        final_result = connector_module.process_concentration_data(calculator_result)
        # ---

        connector_duration = time.time() - connector_start_time
        PROXY_CONNECTOR_LATENCY.observe(connector_duration)

        if final_result and 'error' not in final_result:
            print(f"Proxy: Connector finished in {connector_duration:.4f}s. Final Result (logged): {json.dumps(final_result)}")
            # In this phase, we just log the final result and return success to the GATEWAY
            return jsonify({"status": "processed_by_connector"}), 200
        else:
            error_msg = f"Connector processing failed on proxy: {final_result}"
            print(f"ERROR: {error_msg}")
            PROXY_ERROR_COUNT.inc()
            return jsonify({"status": "connector_error", "detail": error_msg}), 500 # Error back to gateway

    except Exception as e:
        PROXY_ERROR_COUNT.inc()
        connector_duration = time.time() - connector_start_time
        # Optionally observe latency on error
        # PROXY_CONNECTOR_LATENCY.observe(connector_duration)
        print(f"FATAL Error processing request in Proxy: {type(e).__name__} - {e}")
        print(traceback.format_exc())
        return jsonify({"error": "Internal server error on proxy"}), 500


if __name__ == '__main__':
    print("Python Proxy Service (with Connector) Starting...")
    # Start Prometheus metrics server if not using Flask middleware, or rely on /metrics
    # start_http_server(9091) # Example if needed separately
    app.run(host='0.0.0.0', port=8000) # Proxy listens on 8000 internally
    