# Brave Search MCP Installation Guide
## NVIDIA DGX Spark (GB10)

Brave Search is a privacy-respecting web search engine with an official API. This guide sets up
the Brave Search MCP (Model Context Protocol) server so that Open WebUI can perform live web
searches during chat sessions.

The setup uses **mcp-proxy** to wrap the stdio-based Brave Search MCP server and expose it as
an HTTP endpoint that Open WebUI can connect to.

- **MCP proxy:** `mcp-brave-search.service` (systemd), port **8765**
- **MCP server package:** `@modelcontextprotocol/server-brave-search` (via npx)
- **Open WebUI endpoint:** `http://192.168.1.45:8765/mcp`
- **Tools exposed:** `brave_web_search`, `brave_local_search`

> **Before starting:** Install all required software listed in [`prerequisites.md`](prerequisites.md).

---

## Why mcp-proxy?

Open WebUI connects to MCP servers via the **Streamable HTTP** transport (HTTP POST/GET with
session IDs). The official Brave Search MCP package (`@modelcontextprotocol/server-brave-search`)
only speaks **stdio** — it is a command-line process, not an HTTP server. `mcp-proxy` bridges
this gap: it spawns the stdio server as a child process and exposes its tools over HTTP so Open
WebUI can reach it.

```
Open WebUI (Docker)
    │  POST http://192.168.1.45:8765/mcp
    ▼
mcp-proxy  (port 8765, host process)
    │  stdin/stdout pipe
    ▼
npx @modelcontextprotocol/server-brave-search
    │  HTTPS
    ▼
api.search.brave.com
```

---

## Prerequisites

- Node.js 18+ and npm/npx (pre-installed on DGX Spark — verify with `node --version`)
- Miniforge Python (`/usr/local/miniforge3/`) for `mcp-proxy`
- Open WebUI running on port 3000
- A Brave Search API key (free tier: 2 000 queries/month)

```bash
# Verify Node.js and npx
node --version    # v18.19.1
npx --version     # 9.2.0

# Verify Python
/usr/local/miniforge3/bin/python3 --version   # Python 3.13.x
```

---

## 1. Get a Brave Search API Key

1. Go to `https://brave.com/search/api/`
2. Sign up and create a new API application
3. Copy the **API Key** from the dashboard — it looks like `BSAxxx...`

Free tier allows **2 000 queries/month**. Paid tiers are available for higher volume.

---

## 2. Install mcp-proxy

`mcp-proxy` is a Python package that bridges stdio MCP servers to HTTP.

```bash
/usr/local/miniforge3/bin/pip install mcp-proxy
```

Verify:

```bash
/usr/local/miniforge3/bin/mcp-proxy --version
# mcp-proxy, version 0.12.0
```

---

## 3. Create the Log Directory

```bash
sudo mkdir -p /var/log/mcp-proxy
sudo chown sysadmin:sysadmin /var/log/mcp-proxy
```

---

## 4. Systemd Service — `/etc/systemd/system/mcp-brave-search.service`

The service starts mcp-proxy on boot. The `-e` flag passes the API key directly to the spawned
npx process. `--host 0.0.0.0` is required so the Open WebUI Docker container can reach the
service (Docker containers cannot reach `127.0.0.1` on the host).

```bash
sudo tee /etc/systemd/system/mcp-brave-search.service > /dev/null << 'EOF'
[Unit]
Description=MCP Proxy — Brave Search
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=sysadmin
Group=sysadmin

ExecStart=/usr/local/miniforge3/bin/mcp-proxy \
    --host 0.0.0.0 \
    --port 8765 \
    -e BRAVE_API_KEY <YOUR_API_KEY_HERE> \
    -- npx -y @modelcontextprotocol/server-brave-search

Restart=on-failure
RestartSec=5s
KillSignal=SIGTERM
TimeoutStopSec=30s

StandardOutput=append:/var/log/mcp-proxy/mcp-brave-search.log
StandardError=append:/var/log/mcp-proxy/mcp-brave-search.log

[Install]
WantedBy=multi-user.target
EOF
```

Replace `<YOUR_API_KEY_HERE>` with your actual Brave API key, then enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable mcp-brave-search.service
sudo systemctl start mcp-brave-search.service
sudo systemctl status mcp-brave-search.service
```

Verify it is listening:

```bash
ss -tlnp | grep 8765
# LISTEN 0  2048  0.0.0.0:8765  0.0.0.0:*  users:(("mcp-proxy",...))
```

---

## 5. Register with Open WebUI

Open WebUI's MCP client connects to the full endpoint URL. Run this once to register Brave Search:

```bash
curl -s -X POST http://localhost:3000/api/v1/configs/tool_servers \
  -H "Authorization: Bearer <YOUR_OPENWEBUI_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "TOOL_SERVER_CONNECTIONS": [
      {
        "url": "http://192.168.1.45:8765/mcp",
        "path": "/mcp",
        "type": "mcp",
        "auth_type": "none",
        "key": "",
        "config": {"enable": true},
        "info": {"id": "brave-search", "name": "Brave Search"}
      }
    ]
  }'
```

> **Important:** The `url` field must include the full path (`/mcp`). Open WebUI passes the
> `url` value directly to its MCP client — the `path` field is used for display only.

Get your API key from **Open WebUI → Admin Panel → Account → API Keys**.

---

## 6. Verify the Connection

```bash
# Confirm Open WebUI can reach and initialise the MCP server
curl -s -X POST http://localhost:3000/api/v1/configs/tool_servers/verify \
  -H "Authorization: Bearer <YOUR_OPENWEBUI_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "http://192.168.1.45:8765/mcp",
    "path": "/mcp",
    "type": "mcp",
    "auth_type": "none",
    "key": "",
    "config": {"enable": true},
    "info": {"id": "brave-search", "name": "Brave Search"}
  }'
```

A successful response lists the two available tools:

```json
{
  "status": true,
  "specs": [
    {"name": "brave_web_search", "description": "Performs a web search ..."},
    {"name": "brave_local_search", "description": "Searches for local businesses ..."}
  ]
}
```

---

## 7. Using Brave Search in Open WebUI

### Via the Chat UI

1. Open `http://192.168.1.45:3000` and start a new chat.
2. Click the **+** button or **Tools** (wrench) icon at the bottom of the input bar.
3. Toggle **Brave Search** on.
4. Ask a question that requires current information:

   > *"What are the latest llama.cpp performance improvements?"*

   > *"Search for current NVIDIA GB10 benchmark results."*

   > *"Find coffee shops near downtown San Jose."*

The model will call `brave_web_search` or `brave_local_search` automatically, show you the
search it ran, and cite results in its answer.

### Via the API

```bash
curl -s -X POST http://localhost:3000/api/chat/completions \
  -H "Authorization: Bearer <YOUR_OPENWEBUI_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-oss-120b",
    "stream": false,
    "chat_id": "brave-test-1",
    "tool_ids": ["server:mcp:brave-search"],
    "messages": [
      {"role": "user", "content": "Search the web for the latest llama.cpp release notes."}
    ]
  }' | python3 -m json.tool
```

The `tool_ids` field activates Brave Search for that request. Without it the model will not
use the tool even if it is registered.

---

## 8. Available Tools

### `brave_web_search`

General web search — articles, news, documentation, any public web content.

| Parameter | Type | Description |
|---|---|---|
| `query` | string | Search query (max 400 chars / 50 words) |
| `count` | number | Results to return (1–20, default 10) |
| `offset` | number | Pagination offset (max 9, default 0) |

**Example prompts:**
- *"Search for the latest CUDA 13 release notes"*
- *"What is the current stable version of Go?"*
- *"Find recent news about Oracle APEX 26.1"*

### `brave_local_search`

Local business and places search — returns addresses, ratings, phone numbers, opening hours.

| Parameter | Type | Description |
|---|---|---|
| `query` | string | Local search query (e.g. "pizza near Central Park") |
| `count` | number | Results to return (1–20, default 5) |

**Example prompts:**
- *"Find GPU repair shops near San Jose, CA"*
- *"Best Thai restaurants in downtown Austin"*

---

## 9. Updating the API Key

If you need to rotate the API key:

```bash
sudo sed -i 's|-e BRAVE_API_KEY .*|-e BRAVE_API_KEY <NEW_KEY> \\|' \
    /etc/systemd/system/mcp-brave-search.service

sudo systemctl daemon-reload
sudo systemctl restart mcp-brave-search.service
```

---

## 10. Service Management

```bash
sudo systemctl status mcp-brave-search.service
sudo systemctl restart mcp-brave-search.service
sudo systemctl stop mcp-brave-search.service

# View logs
tail -f /var/log/mcp-proxy/mcp-brave-search.log
```

---

## Key Paths

| Path | Purpose |
|---|---|
| `/etc/systemd/system/mcp-brave-search.service` | Systemd unit |
| `/var/log/mcp-proxy/mcp-brave-search.log` | Log file |
| `/usr/local/miniforge3/bin/mcp-proxy` | mcp-proxy binary |
| `http://192.168.1.45:8765/mcp` | MCP HTTP endpoint (Streamable HTTP) |
| `http://192.168.1.45:8765/sse` | MCP SSE endpoint (legacy clients) |
| `https://brave.com/search/api/` | Brave API key management |
