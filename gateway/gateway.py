from flask import Flask, request, jsonify
from prometheus_client import Counter, Histogram, start_http_server
import requests
import json
import traceback
import logging.config
import yaml
import os
from concentration_calculator_module import ConcentrationCalculatorModule

# Load logging configuration
with open('/app/config/logging.yaml', 'r') as f:
    config = yaml.safe_load(f)
    config['handlers']['file']['filename'] = config['handlers']['file']['filename'] % {'container_name': os.getenv('HOSTNAME', 'unknown')}
    logging.config.dictConfig(config)

logger = logging.getLogger('gateway')

# Prometheus metrics
REQUEST_COUNT = Counter('gateway_requests_total', 'Total number of requests processed')
REQUEST_LATENCY = Histogram('gateway_request_duration_seconds', 'Request latency in seconds')
ERROR_COUNT = Counter('gateway_errors_total', 'Total number of errors')

app = Flask(__name__)
concentration_calculator = ConcentrationCalculatorModule()

# Start Prometheus metrics server
start_http_server(9090)

@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy'}), 200

@app.route('/metrics')
def metrics():
    return jsonify({'status': 'metrics endpoint available at :9090/metrics'}), 200

@app.route('/', methods=['POST'])
def process_eeg():
    REQUEST_COUNT.inc()
    request_timer = REQUEST_LATENCY.time()
    
    try:
        if not request.is_json:
            ERROR_COUNT.inc()
            logger.error("Non-JSON request received")
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
            logger.error("Missing EEG data in request")
            return jsonify({
                "error": {
                    "code": 400,
                    "message": "Missing required 'eeg_data' field"
                }
            }), 400

        try:
            concentration_result = concentration_calculator.calculate_concentration(eeg_data)
            if concentration_result.get('concentration_level') == 'ERROR':
                ERROR_COUNT.inc()
                logger.error(f"Error processing EEG data: {concentration_result.get('error')}")
                return jsonify({
                    "error": {
                        "code": 422,
                        "message": f"Error processing EEG data: {concentration_result.get('error')}"
                    }
                }), 422

            logger.info(f"Successfully processed EEG data: {concentration_result}")
            return jsonify(concentration_result), 200

        except Exception as e:
            ERROR_COUNT.inc()
            logger.error(f"Error processing concentration: {str(e)}")
            return jsonify({
                "error": {
                    "code": 500,
                    "message": f"Internal processing error: {str(e)}"
                }
            }), 500

    except Exception as e:
        ERROR_COUNT.inc()
        logger.error(f"Unexpected error: {str(e)}")
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