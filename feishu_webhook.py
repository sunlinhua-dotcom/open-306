#!/usr/bin/env python3
"""
Feishu Card Action Webhook Server (Zeabur Cloud Version)
Receives button click events from Feishu interactive cards.
Stores choices in /tmp/feishu_card_choices/ for polling.
Returns updated card on button click.
"""
import json
import os
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

PORT = int(os.environ.get("WEBHOOK_PORT", os.environ.get("PORT", "8080")))
CHOICE_DIR = Path("/tmp/feishu_card_choices")
CHOICE_DIR.mkdir(exist_ok=True)


class FeishuCardHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'{"error":"bad json"}')
            return

        # Feishu URL verification challenge
        if data.get("type") == "url_verification":
            challenge = data.get("challenge", "")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"challenge": challenge}).encode())
            print(f"[OK] Challenge: {challenge[:20]}...", flush=True)
            return

        # Card action callback
        action = data.get("action") or {}
        value = action.get("value") or {}
        chosen_action = value.get("action", "")
        card_id = value.get("card_id", "")

        if chosen_action and card_id:
            choice_file = CHOICE_DIR / f"{card_id}.json"
            choice_data = {
                "action": chosen_action,
                "open_id": data.get("open_id", ""),
                "message_id": data.get("open_message_id", ""),
                "timestamp": time.time(),
            }
            choice_file.write_text(json.dumps(choice_data))
            print(f"[OK] {chosen_action} for {card_id}", flush=True)

            label_map = {
                "use_gemini": "✅ 已选择 Gemini — 正在执行...",
                "use_qwen": "✅ 已选择千问 — 正在执行...",
            }
            result_text = label_map.get(chosen_action, f"✅ 已选择: {chosen_action}")

            response_card = {
                "config": {"wide_screen_mode": True},
                "header": {
                    "title": {"content": "✅ 已确认", "tag": "plain_text"},
                    "template": "green",
                },
                "elements": [
                    {"tag": "div", "text": {"content": result_text, "tag": "plain_text"}},
                ],
            }

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response_card).encode())
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{}')

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ok", "port": PORT}).encode())

    def log_message(self, format, *args):
        print(f"[{time.strftime('%H:%M:%S')}] {format % args}", flush=True)


if __name__ == "__main__":
    print(f"🚀 Feishu Webhook Server on port {PORT}", flush=True)
    HTTPServer(("0.0.0.0", PORT), FeishuCardHandler).serve_forever()
