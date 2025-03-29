from flask import Flask, request, jsonify
from prometheus_client import Counter, Histogram, start_http_server, make_wsgi_app
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from concentration_calculator_module import ConcentrationCalculatorModule
import time # Make sure time is imported if not already

# Prometheus metrics
REQUEST_COUNT = Counter('gateway_requests_total', 'Total number of requests processed')
REQUEST_LATENCY = Histogram('gateway_request_duration_seconds', 'Request latency in seconds')
ERROR_COUNT = Counter('gateway_errors_total', 'Total number of errors')

app = Flask(__name__)
concentration_calculator = ConcentrationCalculatorModule()

# Add metrics endpoint
app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {
    '/metrics': make_wsgi_app()
})

@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy'}), 200

@app.route('/', methods=['POST'])
def process_eeg():
    REQUEST_COUNT.inc()
    start_time = time.time() # Record start time manually

    try:
        if not request.is_json:
            ERROR_COUNT.inc()
            return jsonify({ ... }), 415 # Keep error handling

        data = request.get_json()
        eeg_data = data.get("eeg_data")

        if not eeg_data:
            ERROR_COUNT.inc()
            return jsonify({ ... }), 400 # Keep error handling

        # --- Perform the main processing ---
        concentration_result = concentration_calculator.calculate_concentration(eeg_data)
        # --- Processing done ---

        # --- Observe latency ONLY on successful processing (or adjust as needed) ---
        # Calculate duration and observe *before* returning success
        duration = time.time() - start_time
        REQUEST_LATENCY.observe(duration)
        # --- Observation done ---

        return jsonify(concentration_result), 200

    except Exception as e:
        ERROR_COUNT.inc()
        # Observe latency even on error if desired, otherwise skip
        duration = time.time() - start_time
        REQUEST_LATENCY.observe(duration)
        print(f"Error processing request: {e}") # Log the actual exception
        # Add traceback logging for better debugging if needed
        import traceback
        print(traceback.format_exc())
        return jsonify({
            "error": {
                "code": 500,
                "message": "Internal server error"
            }
        }), 500
    # No finally block needed for observation with this manual approach

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)