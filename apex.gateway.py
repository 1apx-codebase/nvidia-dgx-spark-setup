#!/usr/bin/env python3
"""Injects stream:false and chat_id into APEX requests before forwarding to Open WebUI."""
import json
import http.server
import socketserver
import urllib.request
import urllib.error
import logging
import os
import sys
import uuid

BACKEND = os.environ.get(
    "APEX_BACKEND",
    "http://192.168.1.45:3000/api/chat/completions"
)

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format="%(asctime)s %(levelname)s %(message)s"
)


class StreamProxy(http.server.BaseHTTPRequestHandler):

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)

        try:
            body = json.loads(raw)
            body["stream"] = False
            if "chat_id" not in body:
                body["chat_id"] = str(uuid.uuid4())
            raw = json.dumps(body).encode("utf-8")
            logging.info("model=%s chat_id=%s stream=false", body.get("model", "unknown"), body["chat_id"])
        except ValueError:
            logging.warning("Non-JSON body, forwarding as-is")

        req = urllib.request.Request(BACKEND, data=raw, method="POST")
        for k, v in self.headers.items():
            if k.lower() in ("host", "content-length", "transfer-encoding"):
                continue
            req.add_header(k, v)
        req.add_header("Content-Length", str(len(raw)))
        req.add_header("Content-Type", "application/json")

        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = resp.read()
                self.send_response(resp.status)
                for k, v in resp.headers.items():
                    if k.lower() == "transfer-encoding":
                        continue
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(data)
        except urllib.error.HTTPError as e:
            data = e.read()
            self.send_response(e.code)
            for k, v in e.headers.items():
                if k.lower() == "transfer-encoding":
                    continue
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(data)
        except urllib.error.URLError as e:
            logging.error("Backend unreachable: %s", e.reason)
            self.send_response(503)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "backend unavailable", "detail": str(e.reason)}).encode())

    def log_message(self, fmt, *args):
        pass


class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", 8766), StreamProxy)
    logging.info("Listening on 0.0.0.0:8766 → %s", BACKEND)
    server.serve_forever()
