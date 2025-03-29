from flask import Flask, request, jsonify
from prometheus_client import Counter, Histogram, start_http_server, make_wsgi_app
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from concentration_calculator_module import ConcentrationCalculatorModule

# Prometheus metrics
REQUEST_COUNT = Counter('gateway_requests_total', 'Total number of requests processed')
REQUEST_LATENCY = Histogram('gateway_request_duration_seconds', 'Request latency in seconds')
ERROR_COUNT = Counter('gateway_errors_total', 'Total number of errors')

app = Flask(__name__)
concentration_calculator = ConcentrationCalculatorModule()

# Add metrics endpoint to the Flask app
app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {
    '/metrics': make_wsgi_app()
})

@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy'}), 200

@app.route('/', methods=['POST'])
def process_eeg():
    REQUEST_COUNT.inc()
    request_timer = REQUEST_LATENCY.time()
    
    try:
        if not request.is_json:
            ERROR_COUNT.inc()
            return jsonify({
                "error": {
                    "code": 415,
                    "message": "Only JSON content type is supported"
                }
            }), 415

        data = request.get_json()
        eeg_data = data.get("eeg_data")
        
        if not eeg_data:
            ERROR_COUNT.inc()
            return jsonify({
                "error": {
                    "code": 400,
                    "message": "Missing required 'eeg_data' field"
                }
            }), 400

        concentration_result = concentration_calculator.calculate_concentration(eeg_data)
        return jsonify(concentration_result), 200

    except Exception as e:
        ERROR_COUNT.inc()
        return jsonify({
            "error": {
                "code": 500,
                "message": "Internal server error"
            }
        }), 500
    finally:
        request_timer.observe()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)