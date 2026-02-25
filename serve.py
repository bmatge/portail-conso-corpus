#!/usr/bin/env python3
"""Serveur local avec proxy CORS pour les API LLM."""

import http.server
import json
import urllib.request
import urllib.error
import sys

PORT = 8888
PROXY_PATH = "/proxy/"


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_OPTIONS(self):
        """Handle CORS preflight."""
        if self.path.startswith(PROXY_PATH):
            self.send_response(204)
            self._cors_headers()
            self.end_headers()
        else:
            super().do_OPTIONS()

    def do_POST(self):
        if not self.path.startswith(PROXY_PATH):
            self.send_error(404)
            return

        # Extract target URL: /proxy/https://albert.api.etalab.gouv.fr/v1/...
        target_url = self.path[len(PROXY_PATH):]
        if not target_url.startswith("http"):
            self.send_error(400, "URL cible invalide")
            return

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
        print(f"Proxy:   http://localhost:{port}/proxy/<URL_API>")
        print("Ctrl+C pour arrêter")
        srv.serve_forever()
