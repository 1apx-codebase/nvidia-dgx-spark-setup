#!/usr/bin/env python3
"""
Proxy: translates OpenAI Responses API (/v1/responses) to Chat Completions
(/v1/chat/completions) for llama-swap compatibility.
All other paths are forwarded unchanged.
"""
import http.server, urllib.request, json, uuid, time, sys

TARGET = "http://localhost:8080"
PORT = 8090


def input_to_messages(input_list):
    messages = []
    for item in input_list:
        role = item.get("role", "user")
        content = item.get("content", "")
        if isinstance(content, list):
            parts = [c.get("text", "") for c in content if c.get("type") in ("input_text", "text")]
            content = "\n".join(parts)
        messages.append({"role": role, "content": content})
    return messages


def text_format_to_response_format(text_fmt):
    if not text_fmt:
        return None
    fmt_type = text_fmt.get("type", "text")
    if fmt_type == "json_schema":
        return {
            "type": "json_schema",
            "json_schema": {
                "name": text_fmt.get("name", "response"),
                "strict": text_fmt.get("strict", True),
                "schema": text_fmt.get("schema", {}),
            }
        }
    elif fmt_type == "json_object":
        return {"type": "json_object"}
    return None


def chat_response_to_responses(chat_resp, req_id):
    choice = chat_resp.get("choices", [{}])[0]
    text = choice.get("message", {}).get("content", "")
    usage = chat_resp.get("usage", {})
    return {
        "id": req_id,
        "object": "response",
        "created_at": int(time.time()),
        "model": chat_resp.get("model", ""),
        "output": [{
            "type": "message",
            "id": "msg_" + req_id,
            "role": "assistant",
            "content": [{"type": "output_text", "text": text, "annotations": []}]
        }],
        "usage": {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        },
        "status": "completed",
    }


class Proxy(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[llama-responses-proxy] {fmt % args}", flush=True)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        if self.path.rstrip("/").endswith("/responses"):
            self._handle_responses(body)
        else:
            self._forward(self.path, body)

    def do_GET(self):
        self._forward(self.path, None)

    def _handle_responses(self, body):
        req_id = "resp_" + uuid.uuid4().hex[:16]
        try:
            req = json.loads(body)
        except Exception as e:
            self.send_error(400, str(e))
            return

        cc_req = {
            "model": req.get("model", ""),
            "messages": input_to_messages(req.get("input", [])),
        }
        rf = text_format_to_response_format(req.get("text", {}).get("format"))
        if rf:
            cc_req["response_format"] = rf
        if "max_output_tokens" in req:
            cc_req["max_tokens"] = req["max_output_tokens"]

        print(f"[llama-responses-proxy] /v1/responses → /v1/chat/completions "
              f"model={cc_req['model']} rf={cc_req.get('response_format', {}).get('type')}", flush=True)

        cc_body = json.dumps(cc_req).encode()
        fwd_req = urllib.request.Request(
            TARGET + "/v1/chat/completions", cc_body,
            {"Content-Type": "application/json", "Content-Length": str(len(cc_body))}
        )
        try:
            resp = urllib.request.urlopen(fwd_req, timeout=300)
            cc_resp = json.loads(resp.read())
            out = chat_response_to_responses(cc_resp, req_id)
            out_bytes = json.dumps(out).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(out_bytes)))
            self.end_headers()
            self.wfile.write(out_bytes)
        except urllib.error.HTTPError as e:
            data = e.read()
            print(f"[llama-responses-proxy] upstream error {e.code}: {data[:200]}", flush=True)
            self.send_response(e.code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(data)

    def _forward(self, path, body):
        headers = {k: v for k, v in self.headers.items()}
        fwd_req = urllib.request.Request(TARGET + path, body, headers)
        try:
            resp = urllib.request.urlopen(fwd_req, timeout=300)
            data = resp.read()
            self.send_response(resp.status)
            for k, v in resp.getheaders():
                if k.lower() not in ("transfer-encoding",):
                    self.send_header(k, v)
            self.end_headers()
            self.wfile.write(data)
        except urllib.error.HTTPError as e:
            data = e.read()
            self.send_response(e.code)
            self.end_headers()
            self.wfile.write(data)


if __name__ == "__main__":
    server = http.server.HTTPServer(("0.0.0.0", PORT), Proxy)
    print(f"[llama-responses-proxy] listening on :{PORT}, forwarding to {TARGET}", flush=True)
    server.serve_forever()
