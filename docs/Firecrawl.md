# Firecrawl

Self-hosted web scraping and AI extraction service running via Docker Compose, backed by the local llama-swap LLM stack.

## Overview

[Firecrawl](https://github.com/mendableai/firecrawl) converts any URL into clean markdown or structured JSON. The local setup uses pre-built images (no local build step) and routes AI extraction calls through `gpt-oss-120b` via llama-swap.

```
Client
  │
  ▼
Firecrawl API  :3002   (docker: firecrawl-api-1)
  │  AI extraction calls  →  /v1/responses
  ▼
llama-responses-proxy  :8090   (systemd)
  │  translated to  →  /v1/chat/completions
  ▼
llama-swap  :8080
  │
  ▼
gpt-oss-120b  (llama-server)
```

[![Firecrawl architecture](images/firecrawl-architecture.jpg)](images/firecrawl-architecture.jpg)

### Why the proxy?

Firecrawl uses Vercel AI SDK v6 (`@ai-sdk/openai` v3), which sends all structured-output requests to the OpenAI **Responses API** (`POST /v1/responses`). llama-server implements this endpoint but ignores the `text.format.json_schema` field, returning plain text instead of JSON. The proxy intercepts Responses API calls, converts them to Chat Completions format (which llama-server handles correctly), and converts the response back.

---

## Locations

| Item | Path |
|---|---|
| Repo | `/home/sysadmin/codebase/firecrawl/` |
| Config | `/home/sysadmin/codebase/firecrawl/.env` |
| Proxy script | `/home/sysadmin/codebase/bin/llama-responses-proxy.py` |
| Proxy unit | `/etc/systemd/system/llama-responses-proxy.service` |
| Manager script | `/home/sysadmin/codebase/bin/init.firecrawl` |

---

## Service Management

```bash
init.firecrawl start        # start proxy + docker stack
init.firecrawl stop         # stop stack + proxy
init.firecrawl restart      # stop then start
init.firecrawl status       # proxy status, container list, API health check
init.firecrawl logs         # tail Firecrawl API container logs
init.firecrawl logs proxy   # tail llama-responses-proxy logs
```

The proxy is a standalone systemd service and can also be managed directly:

```bash
sudo systemctl status llama-responses-proxy.service
sudo systemctl restart llama-responses-proxy.service
```

---

## Configuration

**`/home/sysadmin/codebase/firecrawl/.env`**

```env
PORT=3002
HOST=0.0.0.0
USE_DB_AUTHENTICATION=false
BULL_AUTH_KEY=CHANGEME

# AI extraction — routed through llama-responses-proxy → llama-swap
OPENAI_BASE_URL=http://host.docker.internal:8090/v1
OPENAI_API_KEY=not-needed
MODEL_NAME=gpt-oss-120b
```

`OPENAI_BASE_URL` points to the proxy on port 8090 (not llama-swap directly on 8080). `MODEL_NAME` must be a model registered in llama-swap; it is also used as the model label in every LLM call so pricing lookup warnings for unknown names are harmless.

---

## Docker Compose Stack

Six containers, all using pre-built `ghcr.io/firecrawl/` images (no local build):

| Container | Image | Role |
|---|---|---|
| `firecrawl-api-1` | `ghcr.io/firecrawl/firecrawl` | API + queue workers |
| `firecrawl-playwright-service-1` | `ghcr.io/firecrawl/playwright-service:latest` | Headless browser scraping |
| `firecrawl-nuq-postgres-1` | `ghcr.io/firecrawl/nuq-postgres:latest` | Job queue persistence |
| `firecrawl-redis-1` | `redis:alpine` | Rate limiting / caching |
| `firecrawl-rabbitmq-1` | `rabbitmq:3-management` | Job queue broker |
| `firecrawl-foundationdb-1` | `foundationdb/foundationdb:7.3.63` | Experimental queue backend |

The `build:` directives in `docker-compose.yaml` are commented out and replaced with `image:` for all three Firecrawl-specific services.

---

## API Usage

All examples target `http://localhost:3002`. Replace with `https://api.1apx.com` for external access via the nginx gateway.

---

### 1. Scrape a page to Markdown

```bash
curl -s http://localhost:3002/v2/scrape \
  -H "Content-Type: application/json" \
  -d '{"url":"https://news.ycombinator.com","formats":["markdown"]}' \
  | jq '.data.markdown'
```

---

### 2. Get page metadata only

Useful for title, description, og-image, and other head tags without fetching the body:

```bash
curl -s http://localhost:3002/v2/scrape \
  -H "Content-Type: application/json" \
  -d '{"url":"https://github.com/mendableai/firecrawl","formats":["markdown"]}' \
  | jq '.data.metadata'
```

Returns: `title`, `description`, `ogTitle`, `ogImage`, `statusCode`, `sourceURL`, etc.

---

### 3. AI extraction — prompt only (no schema)

Simplest form: describe what you want in plain English. Returns unstructured text:

```bash
curl -s http://localhost:3002/v2/scrape \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://news.ycombinator.com",
    "formats": [{"type": "json", "prompt": "List the top 5 story titles."}]
  }' | jq '.data.json'
```

---

### 4. AI extraction — structured JSON with schema

Provide a schema with `additionalProperties: false` and all fields in `required` at every level (required for llama.cpp strict grammar mode):

```bash
curl -s http://localhost:3002/v2/scrape \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://news.ycombinator.com",
    "formats": [
      {
        "type": "json",
        "prompt": "Extract the top 5 story titles and their point scores.",
        "schema": {
          "type": "object",
          "additionalProperties": false,
          "required": ["stories"],
          "properties": {
            "stories": {
              "type": "array",
              "items": {
                "type": "object",
                "additionalProperties": false,
                "required": ["title", "score"],
                "properties": {
                  "title": {"type": "string"},
                  "score": {"type": "integer"}
                }
              }
            }
          }
        }
      }
    ]
  }' | jq '.data.json'
```

**Product page example** — extract price and availability from an e-commerce URL:

```bash
curl -s http://localhost:3002/v2/scrape \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.amazon.com/dp/B0C825L5TN",
    "formats": [
      {
        "type": "json",
        "prompt": "Extract the product name, current price, and availability status.",
        "schema": {
          "type": "object",
          "additionalProperties": false,
          "required": ["name", "price", "available"],
          "properties": {
            "name":      {"type": "string"},
            "price":     {"type": "string"},
            "available": {"type": "boolean"}
          }
        }
      }
    ]
  }' | jq '.data.json'
```

---

### 5. Markdown + JSON in one request

Fetch both the clean text and structured data in a single call:

```bash
curl -s http://localhost:3002/v2/scrape \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://en.wikipedia.org/wiki/NVIDIA_GB10",
    "formats": [
      "markdown",
      {
        "type": "json",
        "prompt": "Extract the chip name, release year, and memory bandwidth.",
        "schema": {
          "type": "object",
          "additionalProperties": false,
          "required": ["chip", "year", "bandwidth_GBps"],
          "properties": {
            "chip":            {"type": "string"},
            "year":            {"type": "integer"},
            "bandwidth_GBps":  {"type": "number"}
          }
        }
      }
    ]
  }' | jq '{json: .data.json, markdown_chars: (.data.markdown | length)}'
```

---

### 6. Web search

Returns a list of matching URLs with title and description snippets. Firecrawl uses SearXNG internally when `SEARXNG_ENDPOINT` is configured:

```bash
curl -s http://localhost:3002/v2/search \
  -H "Content-Type: application/json" \
  -d '{"query":"NVIDIA GB10 DGX Spark benchmarks","limit":5}' \
  | jq '[.data[] | {title, url, description}]'
```

---

### 7. Crawl a site (async)

Crawl submits a background job and returns immediately with an ID. Poll until `status` is `completed`:

```bash
# Submit
JOB=$(curl -s http://localhost:3002/v1/crawl \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://docs.firecrawl.dev",
    "limit": 20,
    "scrapeOptions": {"formats": ["markdown"]}
  }' | jq -r '.id')

echo "Job: $JOB"

# Poll until done
while true; do
  STATUS=$(curl -s "http://localhost:3002/v1/crawl/$JOB" | jq -r '.status')
  echo "Status: $STATUS"
  [ "$STATUS" = "completed" ] && break
  sleep 5
done

# Fetch results
curl -s "http://localhost:3002/v1/crawl/$JOB" \
  | jq '[.data[] | {url: .metadata.sourceURL, chars: (.markdown | length)}]'
```

---

### 8. Python example

```python
import requests

resp = requests.post("http://localhost:3002/v2/scrape", json={
    "url": "https://news.ycombinator.com",
    "formats": [
        {
            "type": "json",
            "prompt": "Extract the top 3 stories with title and score.",
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["stories"],
                "properties": {
                    "stories": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["title", "score"],
                            "properties": {
                                "title": {"type": "string"},
                                "score": {"type": "integer"},
                            },
                        },
                    }
                },
            },
        }
    ],
})

data = resp.json()
for story in data["data"]["json"]["stories"]:
    print(f"{story['score']:4d}  {story['title']}")
```

---

### 9. External access via API gateway

All endpoints are available through `https://api.1apx.com` with no additional auth (the gateway is unauthenticated by default):

```bash
# Scrape from anywhere on the internet
curl -s https://api.1apx.com/v2/scrape \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com","formats":["markdown"]}' \
  | jq '.data.metadata.title'

# AI extraction via gateway
curl -s https://api.1apx.com/v2/scrape \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://news.ycombinator.com",
    "formats": [{"type": "json", "prompt": "What is the top story?",
      "schema": {"type": "object", "additionalProperties": false,
        "required": ["title"], "properties": {"title": {"type": "string"}}}}]
  }' | jq '.data.json'
```

---

## Schema Tips

- Always set `"additionalProperties": false` on every object in the schema, including nested ones.
- Always put every property name in the `"required"` array — optional/nullable fields should use `"type": ["string", "null"]` and still be listed in `required`.
- Avoid JSON Schema formats (`"format": "date-time"` etc.) — llama.cpp's grammar engine ignores them and the Vercel AI SDK may reject them in strict mode.
- Skip `minimum`/`maximum` constraints — not supported in strict mode.

---

## Switching the AI Model

Update `MODEL_NAME` in `.env` to any model registered in llama-swap, then restart:

```bash
# Edit .env
vim /home/sysadmin/codebase/firecrawl/.env

# Apply
init.firecrawl restart
```

Useful alternatives:

| Model | Trade-off |
|---|---|
| `gpt-oss-120b` | Default. Best quality, ~5–30 s per extraction |
| `Qwen2.5-Coder-32B` | Strong at JSON, faster, loads on demand |
| `Qwen3.5-9B` | Fastest, lower quality |

---

## Open WebUI Integration

Firecrawl integrates with Open WebUI for live web search and URL-based RAG. Configuration is done via the admin API.

### Step 1 — Get an admin token

```bash
curl -s http://localhost:3000/api/v1/auths/signin \
  -H "Content-Type: application/json" \
  -d '{"email":"aviles.virgil@gmail.com","password":"YOUR_PASSWORD"}' \
  | jq -r '.token'
```

Copy the token string printed.

### Step 2 — Configure web search and RAG loader

This script fetches the full config, patches the Firecrawl fields, and POSTs it back in one step:

```bash
TOKEN="paste-token-here"

python3 - <<'PYEOF'
import json, urllib.request

TOKEN = "paste-token-here"
BASE  = "http://localhost:3000"
HDR   = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

req = urllib.request.Request(f"{BASE}/api/v1/retrieval/config", headers=HDR)
cfg = json.loads(urllib.request.urlopen(req).read())

cfg["web"]["ENABLE_WEB_SEARCH"]      = True
cfg["web"]["WEB_SEARCH_ENGINE"]      = "firecrawl"
cfg["web"]["FIRECRAWL_API_BASE_URL"] = "http://172.17.0.1:3002"
cfg["web"]["FIRECRAWL_API_KEY"]      = "none"
cfg["web"]["WEB_LOADER_ENGINE"]      = "firecrawl"

body = json.dumps(cfg).encode()
req2 = urllib.request.Request(f"{BASE}/api/v1/retrieval/config/update",
                               data=body, headers=HDR, method="POST")
resp = json.loads(urllib.request.urlopen(req2).read())
w = resp.get("web", {})
print("FIRECRAWL_API_BASE_URL:", w.get("FIRECRAWL_API_BASE_URL"))
print("WEB_SEARCH_ENGINE:    ", w.get("WEB_SEARCH_ENGINE"))
print("WEB_LOADER_ENGINE:    ", w.get("WEB_LOADER_ENGINE"))
PYEOF
```

### Usage in chat

- **Web search:** click the 🌐 globe icon before sending a message — the LLM will fetch and summarize live pages.
- **RAG from URL:** click the paperclip → paste a URL — Open WebUI fetches the page via Firecrawl and injects it as context.

> **Note:** `172.17.0.1` is the Docker host gateway as seen from the Open WebUI container (which is on the default bridge network). `localhost` and `host.docker.internal` do not work because Open WebUI is not on the same Docker network as Firecrawl.

---

## Proxy Details

**`/home/sysadmin/codebase/bin/llama-responses-proxy.py`**

Listens on `:8090`. For any path other than `/v1/responses`, it passes the request through to llama-swap on `:8080` unchanged. For `/v1/responses`:

1. Converts `input[]` → `messages[]`
2. Converts `text.format` → `response_format`
3. Forwards to `POST /v1/chat/completions` on llama-swap
4. Converts the Chat Completions response back to Responses API shape

The proxy runs as a systemd service (`llama-responses-proxy.service`) and auto-restarts on failure.
