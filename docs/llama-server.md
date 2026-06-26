# llama-server Installation Guide
## NVIDIA DGX Spark (GB10)

llama-server is the HTTP inference server from the [llama.cpp](https://github.com/ggerganov/llama.cpp) project.
On this machine it is built from source with CUDA support for the Blackwell GB10 GPU and installed as a
system binary. llama-swap spawns llama-server instances dynamically to serve models; a separate standalone
`llama-server.service` is also available for direct single-model use.

[![Stack architecture](images/architecture.jpg)](images/architecture.jpg)

> **Before starting:** Install all required software listed in [`prerequisites.md`](prerequisites.md).

---

## Hardware Reference

| Component | Detail |
|---|---|
| Platform | NVIDIA DGX Spark (GB10) |
| CPU | ARM aarch64 — 10× Cortex-X925 (big) + 10× Cortex-A725 (little) |
| Memory | 121 GiB unified (CPU + GPU share same pool) |
| GPU | NVIDIA GB10, compute capability 12.1 (Blackwell) |
| CUDA | 13.0, driver 580.159.03 |
| Storage | 3.7 TB NVMe (`/`) |
| OS | Ubuntu, kernel 6.17.0-1021-nvidia |

---

## Prerequisites

```bash
# Verify CUDA is available
nvcc --version          # should show release 13.0
nvidia-smi              # should show GB10

# Install build tools if missing
sudo apt-get install -y git cmake build-essential
```

---

## 1. Clone llama.cpp

```bash
cd ~/codebase
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp
```

> **Note:** `~/codebase/llama.cpp/` is a live upstream clone. Pull regularly to get the latest
> quantisation support, bug fixes, and new CUDA kernels.

The binary installed as of this documentation was built from commit `1a29907` with the full optimised flag set documented in Section 2.

---

## 2. Build with CUDA

```bash
cd ~/codebase/llama.cpp

cmake -B build \
    -DGGML_CUDA=ON \
    -DGGML_CUDA_F16=ON \
    -DCMAKE_CUDA_ARCHITECTURES="121a-real" \
    -DGGML_CPU_ARM_ARCH=native \
    -DGGML_CPU_KLEIDIAI=ON \
    -DGGML_CUDA_FA_ALL_QUANTS=ON \
    -DGGML_CUDA_COMPRESSION_MODE=speed \
    -DGGML_LTO=ON

cmake --build build --config Release -j 20
```

**Flag explanations:**

| Flag | Reason |
|---|---|
| `-DGGML_CUDA=ON` | Enable CUDA backend |
| `-DGGML_CUDA_F16=ON` | Enable F16 CUDA kernels (Blackwell supports natively) |
| `-DCMAKE_CUDA_ARCHITECTURES="121a-real"` | Target Blackwell SM 12.1 exactly; avoids PTX fallback |
| `-DGGML_CPU_ARM_ARCH=native` | Forces compiler to probe the actual CPU and enable `i8mm`, `sve`, `sve2`, `dotprod` ARM fast paths — CMake auto-detection fails silently without this, leaving these optimised paths out of the binary |
| `-DGGML_CPU_KLEIDIAI=ON` | ARM's optimised kernel library (fetched automatically by CMake); provides faster quantised matmul kernels tuned for the Cortex-X925 big cores |
| `-DGGML_CUDA_FA_ALL_QUANTS=ON` | Enables FlashAttention for all KV cache quantisation types; required for FA to remain active with `--cache-type-k q8_0 --cache-type-v q8_0` (without this flag FA silently falls back for Q8_0) |
| `-DGGML_CUDA_COMPRESSION_MODE=speed` | Compiles CUDA kernels for runtime speed rather than binary size (default is `size`) |
| `-DGGML_LTO=ON` | Link-time optimisation; modest runtime gain (~2–5%) at the cost of longer build time |
| `-j 20` | Use all 20 CPU cores during compilation |

After configuring, verify the ARM fast paths were detected:

```bash
grep "MACHINE_SUPPORTS" build/CMakeCache.txt
# dotprod, i8mm, and sve should show TRUE after a successful configure
```

The build outputs binaries to `~/codebase/llama.cpp/build/bin/`. The primary binary is
`~/codebase/llama.cpp/build/bin/llama-server`.

> Build time is approximately 10–15 minutes on the GB10 with LTO enabled.
> The currently installed binary (`/usr/local/bin/llama-server`, 6.6 MB, built 2026-06-23) was compiled with all flags above.

---

## 3. Install the Binary

```bash
sudo cp ~/codebase/llama.cpp/build/bin/llama-server /usr/local/bin/llama-server
sudo chown sysadmin:sysadmin /usr/local/bin/llama-server
sudo chmod 755 /usr/local/bin/llama-server
```

Verify:

```bash
/usr/local/bin/llama-server --version
ls -lh /usr/local/bin/llama-server   # ~6.6 MB (LTO reduces binary size)
```

---

## 4. Runtime Library Path

llama.cpp's CUDA shared libraries live in the build output directory. The service and llama-swap
both set `LD_LIBRARY_PATH` at runtime — no system-wide ldconfig change is needed.

```
LD_LIBRARY_PATH=/home/sysadmin/codebase/llama.cpp/build/bin
```

This is set via `/etc/default/llama-swap.profile` (for llama-swap) and directly in the
`llama-server.service` unit (for standalone use).

---

## 5. Create the Log Directory

```bash
sudo mkdir -p /var/log/llama
sudo chown sysadmin:sysadmin /var/log/llama
```

---

## 6. Standalone Service Setup

The standalone service runs llama-server with a fixed model (currently gpt-oss-120b) on a fixed port.
This is separate from llama-swap's dynamic management.

### 6a. Profile file — `/etc/default/llama-server.profile`

```bash
sudo tee /etc/default/llama-server.profile > /dev/null << 'EOF'
# Path to binary
LLAMA_BIN=/usr/local/bin/llama-server

# Device/model/runtime args
LLAMA_DEVICE=CUDA0
LLAMA_MODEL=/home/sysadmin/codebase/models/gguf/openai/gpt-oss-120b-MXFP4-GGUF/gpt-oss-120b-mxfp4-00001-of-00003.gguf
LLAMA_HOST=0.0.0.0
LLAMA_PORT=10000

# Extra args (keep as one string)
LLAMA_EXTRA_ARGS="--n-gpu-layers 99 --no-mmap --cont-batching --batch-size 4096 --ubatch-size 1024 --ctx-size 64000 --threads 10 --threads-batch 20 --kv-unified --no-op-offload"
EOF
```

### 6b. Start script — `/usr/local/bin/llama-server-start`

```bash
sudo tee /usr/local/bin/llama-server-start > /dev/null << 'EOF'
#!/usr/bin/env bash
set -euo pipefail

source /etc/default/llama-server.profile

read -ra extra_args <<< "${LLAMA_EXTRA_ARGS:-}"

exec "$LLAMA_BIN" \
  --device "$LLAMA_DEVICE" \
  --model "$LLAMA_MODEL" \
  --host "$LLAMA_HOST" \
  --port "$LLAMA_PORT" \
  "${extra_args[@]}"
EOF
sudo chmod 755 /usr/local/bin/llama-server-start
```

### 6c. Systemd unit — `/etc/systemd/system/llama-server.service`

```bash
sudo tee /etc/systemd/system/llama-server.service > /dev/null << 'EOF'
[Unit]
Description=LLAMA Server
Wants=network-online.target
After=network-online.target docker.service openwebui.service
Requires=docker.service openwebui.service

StartLimitIntervalSec=300
StartLimitBurst=10

[Service]
Type=simple
User=sysadmin
Group=sysadmin
SupplementaryGroups=docker

Environment=LLAMA_LOG_COLORS=1
Environment=LLAMA_LOG_PREFIX=1
Environment=LLAMA_LOG_TIMESTAMPS=1

EnvironmentFile=/etc/default/llama-server.profile

ExecStart=/usr/local/bin/llama-server-start

Restart=always
RestartSec=10

KillSignal=SIGTERM
TimeoutStopSec=60
KillMode=mixed

StandardOutput=append:/var/log/llama/llama-server.log
StandardError=append:/var/log/llama/llama-server.log
LogsDirectory=llama

NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=false
ReadWritePaths=/var/log/llama

[Install]
WantedBy=multi-user.target
EOF
```

### 6d. Enable and start

```bash
sudo systemctl daemon-reload
sudo systemctl enable llama-server.service
sudo systemctl start llama-server.service
sudo systemctl status llama-server.service
```

---

## 7. Verify

```bash
# Check it is serving
curl http://localhost:10000/health

# List available models
curl http://localhost:10000/v1/models | python3 -m json.tool

# Check logs
tail -f /var/log/llama/llama-server.log
```

---

## 8. Service Manager Script

`/home/sysadmin/codebase/bin/init.llama-server` is a helper script for day-to-day management:

```bash
init.llama-server start
init.llama-server stop
init.llama-server restart
init.llama-server reload    # daemon-reload then restart
init.llama-server status
init.llama-server logs      # tail the log file
```

### Script source

```bash
sudo tee /home/sysadmin/codebase/bin/init.llama-server > /dev/null << 'EOF'
#!/usr/bin/env bash
# init.llama-server — llama-server Service Manager
set -euo pipefail
SERVICE="llama-server.service"
LOG_FILE="/var/log/llama/llama-server.log"
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'
info()    { echo -e "${CYAN}[INFO]${RESET}  $*"; }
success() { echo -e "${GREEN}[OK]${RESET}    $*"; }
error()   { echo -e "${RED}[ERROR]${RESET} $*" >&2; }
die()     { error "$*"; exit 1; }
separator() { echo -e "${CYAN}$(printf '─%.0s' {1..60})${RESET}"; }
require_systemctl() { command -v systemctl &>/dev/null || die "systemctl not found."; }
usage() {
    echo -e "\n${BOLD}init.llama-server${RESET} — llama-server Service Manager\n"
    echo -e "${BOLD}COMMANDS${RESET}"
    echo -e "  start | stop | restart | reload | status | logs | help"
}
cmd_start()   { info "Starting ${SERVICE}…"; sudo systemctl start "$SERVICE" && success "Started." || die "Failed."; separator; cmd_status; }
cmd_stop()    { info "Stopping ${SERVICE}…"; sudo systemctl stop "$SERVICE" && success "Stopped." || die "Failed."; }
cmd_restart() { info "Restarting ${SERVICE}…"; sudo systemctl restart "$SERVICE" && success "Restarted." || die "Failed."; separator; cmd_status; }
cmd_reload()  { info "Reloading daemon…"; sudo systemctl daemon-reload && success "Reloaded." || die "Failed."; cmd_restart; }
cmd_status() {
    info "Status of ${SERVICE}:"; separator
    sudo systemctl status "$SERVICE" --no-pager -l || true; separator
    info "Recent logs:"
    local since; since=$(systemctl show "$SERVICE" -p ActiveEnterTimestamp --value 2>/dev/null)
    if [[ -n "$since" && "$since" != "n/a" ]]; then sudo journalctl -u "$SERVICE" --since="$since" --no-pager || true
    else sudo journalctl -u "$SERVICE" -n 20 --no-pager || true; fi; separator
}
cmd_logs() { info "Tailing ${LOG_FILE}  (Ctrl-C to exit)"; separator; sudo tail -f "$LOG_FILE"; }
main() {
    require_systemctl
    case "${1:-help}" in
        start) cmd_start;; stop) cmd_stop;; restart) cmd_restart;;
        reload) cmd_reload;; status) cmd_status;; logs) cmd_logs;;
        help|--help|-h) usage;;
        *) error "Unknown command: '$1'"; usage; exit 1;;
    esac
}
main "$@"
EOF
sudo chmod 755 /home/sysadmin/codebase/bin/init.llama-server
```

---

## 9. Rebuilding After Upstream Updates

```bash
cd ~/codebase/llama.cpp
git pull

# Re-run cmake if new options or upstream CMakeLists changes are expected;
# otherwise cmake --build alone picks up changed source files.
cmake -B build \
    -DGGML_CUDA=ON \
    -DGGML_CUDA_F16=ON \
    -DCMAKE_CUDA_ARCHITECTURES="121a-real" \
    -DGGML_CPU_ARM_ARCH=native \
    -DGGML_CPU_KLEIDIAI=ON \
    -DGGML_CUDA_FA_ALL_QUANTS=ON \
    -DGGML_CUDA_COMPRESSION_MODE=speed \
    -DGGML_LTO=ON

cmake --build build --config Release -j 20

# Replace binary (llama-swap and llama-server.service must be restarted after this)
sudo cp build/bin/llama-server /usr/local/bin/llama-server

sudo systemctl restart llama-swap.service
sudo systemctl restart llama-server.service
```

---

## Key Paths

| Path | Purpose |
|---|---|
| `~/codebase/llama.cpp/` | Source repository |
| `~/codebase/llama.cpp/build/bin/` | Build output, CUDA shared libs |
| `/usr/local/bin/llama-server` | Installed binary (~6.8 MB) |
| `/usr/local/bin/llama-server-start` | Wrapper start script |
| `/etc/default/llama-server.profile` | Runtime configuration |
| `/etc/systemd/system/llama-server.service` | Systemd unit |
| `/var/log/llama/llama-server.log` | Log file |
