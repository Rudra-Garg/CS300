from http.server import BaseHTTPRequestHandler, HTTPServer

import requests


class GatewayHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            response = requests.get('http://proxy:80' + self.path)
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(response.content)
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode())


if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', 8000), GatewayHandler)
    print("Gateway started on port 8000")
    server.serve_forever()
