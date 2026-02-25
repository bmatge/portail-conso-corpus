#!/usr/bin/env python3
"""Serveur local avec proxy CORS pour les API LLM."""

import http.server
import json
import urllib.request
import urllib.error
import sys

PORT = 8888
PROXY_PREFIX = "/proxy-"
API_PATH = "/api/"
API_BACKEND = "http://localhost:8000"


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_OPTIONS(self):
        """Handle CORS preflight."""
        if self.path.startswith(PROXY_PREFIX):
            self.send_response(204)
            self._cors_headers()
            self.end_headers()
        else:
            super().do_OPTIONS()

    def do_GET(self):
        # Proxy /api/* → FastAPI backend
        if self.path.startswith(API_PATH):
            self._proxy_api()
        else:
            super().do_GET()

    def do_POST(self):
        if self.path.startswith(API_PATH):
            self._proxy_api()
            return

        if not self.path.startswith(PROXY_PREFIX):
            self.send_error(404)
            return

        # Extract target URL: /proxy-https/albert.api.etalab.gouv.fr/v1/...
        rest = self.path[len(PROXY_PREFIX):]  # "https/host/path" or "http/host/path"
        slash = rest.find("/")
        if slash < 0:
            self.send_error(400, "URL cible invalide")
            return
        scheme = rest[:slash]   # "https" or "http"
        target_url = f"{scheme}://{rest[slash + 1:]}"

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        # Forward headers (keep auth, content-type)
        fwd_headers = {}
        for h in ("Content-Type", "Authorization", "x-api-key", "anthropic-version",
                   "anthropic-dangerous-direct-browser-access"):
            v = self.headers.get(h)
            if v:
                fwd_headers[h] = v

        req = urllib.request.Request(target_url, data=body, headers=fwd_headers, method="POST")
        try:
            with urllib.request.urlopen(req) as resp:
                resp_body = resp.read()
                self.send_response(resp.status)
                self._cors_headers()
                self.send_header("Content-Type", resp.headers.get("Content-Type", "application/json"))
                self.end_headers()
                self.wfile.write(resp_body)
        except urllib.error.HTTPError as e:
            resp_body = e.read()
            self.send_response(e.code)
            self._cors_headers()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(resp_body)

    def _proxy_api(self):
        """Proxy /api/* requests to FastAPI backend (with SSE streaming support)."""
        target_url = API_BACKEND + self.path
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length else None

        fwd_headers = {"Content-Type": self.headers.get("Content-Type", "application/json")}
        accept = self.headers.get("Accept", "")
        if accept:
            fwd_headers["Accept"] = accept

        req = urllib.request.Request(
            target_url, data=body, method=self.command, headers=fwd_headers,
        )
        try:
            resp = urllib.request.urlopen(req, timeout=120)
            content_type = resp.headers.get("Content-Type", "application/json")
            self.send_response(resp.status)
            self._cors_headers()
            self.send_header("Content-Type", content_type)

            if "text/event-stream" in content_type:
                # Stream SSE responses chunk by chunk
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.end_headers()
                while True:
                    chunk = resp.read(1024)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
            else:
                resp_body = resp.read()
                self.end_headers()
                self.wfile.write(resp_body)
            resp.close()
        except urllib.error.HTTPError as e:
            resp_body = e.read()
            self.send_response(e.code)
            self._cors_headers()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(resp_body)
        except urllib.error.URLError:
            self.send_error(502, "Backend API non disponible (lancer uvicorn sur le port 8000)")

    def _cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers",
                         "Content-Type, Authorization, x-api-key, anthropic-version, "
                         "anthropic-dangerous-direct-browser-access")


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    with http.server.HTTPServer(("", port), Handler) as srv:
        print(f"Serveur: http://localhost:{port}")
        print(f"Proxy:   http://localhost:{port}/proxy-https/<host>/<path>")
        print("Ctrl+C pour arrêter")
        srv.serve_forever()
