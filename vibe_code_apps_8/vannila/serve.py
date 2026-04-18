"""Serve this folder with Python's built-in HTTP server (stdlib only)."""

from __future__ import annotations

import http.server
import os
import socketserver

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)

PORT = int(os.environ.get("PORT", "8080"))
BIND = os.environ.get("BIND", "127.0.0.1")

Handler = http.server.SimpleHTTPRequestHandler
Handler.extensions_map |= {".js": "application/javascript", ".css": "text/css; charset=utf-8"}

if __name__ == "__main__":
    with socketserver.TCPServer((BIND, PORT), Handler) as httpd:
        print(f"Serving {ROOT}")
        print(f"Open http://{BIND}:{PORT}/")
        httpd.serve_forever()
