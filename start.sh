#!/bin/bash
# Start both the OpenClaw Gateway and the Feishu Webhook Server

# Start webhook server in the background on port 19876
python3 /app/feishu_webhook.py &
WEBHOOK_PID=$!
echo "🔔 Feishu webhook started (PID: $WEBHOOK_PID, port: 19876)"

# Start OpenClaw Gateway in the foreground on port 8080
exec npx openclaw gateway --port 8080
