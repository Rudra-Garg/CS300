from http.server import BaseHTTPRequestHandler, HTTPServer
import requests
import json
import traceback
from concentration_calculator_module import ConcentrationCalculatorModule 

concentration_calculator = ConcentrationCalculatorModule() 

class GatewayHandler(BaseHTTPRequestHandler):
    def do_POST(self): # Expecting POST requests from mobile (Client Module)
        try:
            if not self.headers.get('Content-Type') == 'application/json':
                self._send_error(415, "Only JSON content type is supported")
                return

            try:
                content_length = int(self.headers.get('Content-Length', 0))
                if content_length == 0:
                    logger.error("Missing Content-Length header")
                    ERROR_COUNT.inc()
                    self._send_error(411, "Content-Length required")
                    return

                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
            except (ValueError, json.JSONDecodeError) as e:
                self._send_error(400, f"Invalid JSON format: {str(e)}")
                return

            eeg_data = data.get("eeg_data") # Get processed EEG data from Client Module
            if not eeg_data:
                self._send_error(400, "Missing required 'eeg_data' field")
                return

            try:
                concentration_result = concentration_calculator.calculate_concentration(eeg_data)
                if concentration_result.get('concentration_level') == 'ERROR':
                    self._send_error(422, f"Error processing EEG data: {concentration_result.get('error')}")
                    return

                self._send_success(concentration_result)
            except Exception as e:
                self._send_error(500, f"Internal processing error: {str(e)}")

        except Exception as e:
            print(f"Unexpected error in Gateway: {str(e)}")
            traceback.print_exc()
            self._send_error(500, "Internal server error")

    def _send_success(self, data):
        """Send a successful JSON response"""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _send_error(self, code, message):
        """Send an error response with the given code and message"""
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        error_response = {
            "error": {
                "code": code,
                "message": message
            }
        }
        self.wfile.write(json.dumps(error_response).encode())


if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', 8000), GatewayHandler)
    print("Gateway started on port 8000")
    server.serve_forever()