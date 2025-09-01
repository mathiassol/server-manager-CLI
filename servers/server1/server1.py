from http.server import HTTPServer, BaseHTTPRequestHandler
import sys

class CrashHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/crash':
            print("Crashing server on purpose!")
            sys.exit(1)
        else:
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Server is running!")

if __name__ == "__main__":
    server_address = ('', 8000)
    httpd = HTTPServer(server_address, CrashHandler)
    print("Server running on http://localhost:8000/")
    httpd.serve_forever()
