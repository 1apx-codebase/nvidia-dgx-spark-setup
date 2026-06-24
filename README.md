# DGX Spark — AI Inference Stack

This repository contains scripts, configuration, and documentation for the full AI inference
stack running on the **NVIDIA DGX Spark (GB10)**. The stack serves LLM inference locally,
exposes it through a web UI, and integrates with Oracle APEX and live web search.

---

## Architecture

```
Oracle APEX
    │  POST :8766
    ▼
apex-gateway.py          ← injects stream:false + chat_id
    │  POST :3000
    ▼
Open WebUI  (Docker)     ← chat interface, model management, tool calling
    │  OpenAI API :8080
    ▼
llama-swap               ← model router, dynamic process manager
    │  spawns
    ▼
llama-server             ← GPU inference engine (llama.cpp)
    │
    ▼
NVIDIA GB10 GPU          ← 121 GiB unified memory, Blackwell (SM 12.1)
```

---

## Services

| Service | Port | Description | Managed by |
|---|---|---|---|
| `llama-swap` | 8080 | Model router — OpenAI-compatible API, dynamic model loading | systemd |
| `openwebui` | 3000 | Web chat interface (Docker container) | systemd |
| `apex-gateway` | 8766 | HTTP proxy adapting Oracle APEX requests for Open WebUI | systemd |
| `llama-server` | 10000 | Standalone single-model inference server (optional) | systemd |

Check all services at once:

```bash
init.status
```

---

## Quick Reference

| Task | Command |
|---|---|
| Check all services | `init.status` |
| Restart llama-swap | `init.llama-swap restart` |
| Restart Open WebUI | `init.openwebui restart` |
| Restart APEX gateway | `init.apex-gateway restart` |
| Run a model benchmark | `python3 benchmark_models.py --models gpt-oss-120b` |
| View llama-swap logs | `init.llama-swap logs` |
| View Open WebUI logs | `init.openwebui logs` |

---

## Documentation

All installation and operational guides are in [`docs/`](docs/).

### Installation Guides

| Guide | Description |
|---|---|
| [`docs/prerequisites.md`](docs/prerequisites.md) | All required software — install this first. Covers apt packages, CUDA, Go, Docker, Miniforge, and Hugging Face auth. |
| [`docs/llama-server.md`](docs/llama-server.md) | Build llama.cpp from source with optimised CMake flags for the GB10 (ARM KleidiAI, CUDA FA, LTO), install the binary, configure the standalone systemd service. |
| [`docs/llama-swap.md`](docs/llama-swap.md) | Install and configure llama-swap — full annotated config YAML, all 21 registered models, arg macro reference, model download instructions, systemd unit. |
| [`docs/openwebui.md`](docs/openwebui.md) | Deploy Open WebUI in Docker, connect to llama-swap, set context windows per model, register MCP tool servers, upgrade procedure. |
| [`docs/apex-gateway.md`](docs/apex-gateway.md) | Deploy the APEX Gateway proxy — full Python source, systemd unit, Oracle APEX configuration, request flow diagram. |

### Benchmarking

| Guide | Description |
|---|---|
| [`docs/benchmark-guide.md`](docs/benchmark-guide.md) | How to run the benchmark script — CLI reference, metric definitions, examples, tips specific to this setup. |
| [`docs/benchmark_all_models.md`](docs/benchmark_all_models.md) | Full benchmark of all 20 registered models (2026-06-24, 2 iterations). Results summary, per-model detail, and recommendations. |
| [`docs/benchmark_gpt-oss-120b.md`](docs/benchmark_gpt-oss-120b.md) | Detailed benchmark for `gpt-oss-120b` only (2026-06-23, 3 iterations). |

---

## Hardware

| Component | Detail |
|---|---|
| Platform | NVIDIA DGX Spark (GB10) |
| CPU | ARM aarch64 — 10× Cortex-X925 + 10× Cortex-A725 |
| Memory | 121 GiB unified (CPU + GPU share same pool) |
| GPU | NVIDIA GB10, compute capability 12.1 (Blackwell) |
| CUDA | 13.0, driver 580.159.03 |
| Storage | 3.7 TB NVMe |

---

## Models

20 models are registered in llama-swap. The default model (`gpt-oss-120b`) loads at service
start and stays resident. All others load on demand and remain loaded until evicted by memory
pressure.

| Model | Size | Benchmark | Notes |
|---|---|---|---|
| `gpt-oss-120b` | 120B MXFP4 | **55.8 t/s** | **Default — loads at startup.** 131K ctx, ~60 GB |
| `gpt-oss-20b` | 20B Q8_0 | 80.0 t/s | Lightweight fallback, 32K ctx |
| `Qwen3-Coder-REAP-25B` | 25B Q4_K_M | 84.7 t/s | Fastest model; reasoning-enhanced coder |
| `Qwen3-Coder-30B-Q6` | 30B Q6_K | 69.1 t/s | Fast code model, 64K ctx |
| `Qwen3-Coder-30B` | 30B Q8_0 | 60.1 t/s | Fast code model, full precision |
| `Qwen2.5-Coder-32B` | 32B Q8_0 | 6.4 t/s | Dedicated code model, 128K ctx |
| `DeepSeek-R1-70B` | 70B Q5_K_M | 4.0 t/s | Strong reasoning and debugging |
| `Qwen3.5-9B` | 9B Q8_0 | 23.6 t/s | Fast lightweight |

Full model list, benchmark results, and context windows: [`docs/llama-swap.md`](docs/llama-swap.md) · [`docs/benchmark_all_models.md`](docs/benchmark_all_models.md)

---

## Key Paths

| Path | Purpose |
|---|---|
| `/etc/default/llama-swap.yaml` | llama-swap config (models, macros, TTL) |
| `/usr/local/bin/llama-swap` | llama-swap binary |
| `/usr/local/bin/llama-server` | llama-server binary (built from llama.cpp) |
| `~/codebase/llama.cpp/` | llama.cpp source repository |
| `~/codebase/models/gguf/` | Model files (model-shelf layout: `<org>/<repo>/`) |
| `/home/sysadmin/codebase/bin/apex.gateway.py` | APEX Gateway script |
| `/var/log/llama/` | llama-server and llama-swap logs |
| `/var/log/openwebui/` | Open WebUI logs |
| `/var/log/apex-gateway/` | APEX Gateway logs |
