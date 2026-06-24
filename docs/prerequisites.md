# Prerequisites & Software Requirements
## NVIDIA DGX Spark (GB10)

This document lists all software required across the four service installations.
Install everything here before following any individual installation guide.

| Guide | Requires |
|---|---|
| `llama-server.md` | Git, CMake, GCC (build-essential), CUDA, NVIDIA driver, KleidiAI (auto-fetched by CMake) |
| `llama-swap.md` | Go, Git, Make, Miniforge/hf CLI (for model downloads) |
| `openwebui.md` | Docker |
| `apex-gateway.md` | Miniforge (Python 3) |
| `brave-search.md` | Node.js 18+ (npx), Miniforge (mcp-proxy), Brave Search API key |

---

## 1. System Packages

Install with apt. These are required for building llama.cpp from source.

```bash
sudo apt-get update
sudo apt-get install -y \
    git \
    cmake \
    build-essential \
    curl
```

Verify:

```bash
git --version      # git version 2.43.0
cmake --version    # cmake version 3.28.3
gcc --version      # gcc 13.3.0
make --version     # GNU Make 4.3
```

---

## 1b. ARM CPU Optimisation Notes

The GB10's Cortex-X925 cores support `sve`, `sve2`, `i8mm`, `bf16`, and `dotprod` — all of which
llama.cpp can exploit during prompt processing. CMake's auto-detection of these features fails
silently on this machine; they must be forced explicitly via `-DGGML_CPU_ARM_ARCH=native` at
configure time (covered in `llama-server.md`). No additional packages are required — the flag
instructs the compiler to probe the live CPU itself.

KleidiAI (`-DGGML_CPU_KLEIDIAI=ON`) is fetched automatically by CMake via FetchContent when the
flag is set. No manual installation is needed.

---

## 2. NVIDIA Driver & CUDA Toolkit

The NVIDIA driver and CUDA toolkit come pre-installed on the DGX Spark. Verify they are present
before proceeding with the llama.cpp build.

```bash
nvidia-smi         # should show GB10, driver 580.159.03, CUDA 13.0
nvcc --version     # Cuda compilation tools, release 13.0
```

If either command fails, the driver stack needs reinstallation — contact NVIDIA support for the
DGX Spark-specific driver package.

---

## 3. Go

Required for building llama-swap from source. The go.mod requires Go 1.25.4+.

```bash
# Download Go for ARM64 — check https://go.dev/dl/ for the latest version
GO_VERSION="1.25.4"
curl -OL https://go.dev/dl/go${GO_VERSION}.linux-arm64.tar.gz
sudo rm -rf /usr/local/go
sudo tar -C /usr/local -xzf go${GO_VERSION}.linux-arm64.tar.gz
rm go${GO_VERSION}.linux-arm64.tar.gz

# Add to PATH (add to ~/.bashrc or ~/.profile for persistence)
export PATH=$PATH:/usr/local/go/bin
```

Verify:

```bash
go version    # go version go1.25.4 linux/arm64
```

> **Installed version on this machine:** go1.22.2 linux/arm64 (from Ubuntu apt).
> The llama-swap build may require a newer version — check `go.mod` and upgrade if the build fails.

---

## 4. Docker

Required for Open WebUI.

```bash
# Install Docker via the official convenience script
curl -fsSL https://get.docker.com | sudo sh

# Add sysadmin to the docker group so Docker can be used without sudo
sudo usermod -aG docker sysadmin

# Apply group membership without logging out
newgrp docker
```

Enable Docker to start on boot:

```bash
sudo systemctl enable docker
sudo systemctl start docker
```

Verify:

```bash
docker --version    # Docker version 29.2.1
docker ps           # should return empty table, not an error
```

---

## 5. Miniforge (Python 3)

Required for the APEX Gateway. Also provides `hf` (Hugging Face CLI) used to download models
for llama-swap.

```bash
# Download the ARM64 installer
curl -L https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-aarch64.sh \
     -o /tmp/miniforge.sh

# Install to /usr/local/miniforge3 (system-wide, accessible to all users and services)
sudo bash /tmp/miniforge.sh -b -p /usr/local/miniforge3
rm /tmp/miniforge.sh
```

Verify:

```bash
/usr/local/miniforge3/bin/python3 --version    # Python 3.13.x
/usr/local/miniforge3/bin/hf --version         # 1.20.1
```

> **Note:** `huggingface-cli` is deprecated. Use `hf` instead (installed automatically with Miniforge
> via the `huggingface_hub` package).

---

## 6. Hugging Face Authentication (for model downloads)

Models for llama-swap are downloaded from Hugging Face. Some models (e.g., gpt-oss-120b) require
accepting a licence agreement on the Hugging Face website and being authenticated via the CLI.

```bash
# Log in with a Hugging Face access token
/usr/local/miniforge3/bin/hf auth login
# Paste your token when prompted (get one at https://huggingface.co/settings/tokens)
```

Verify access:

```bash
/usr/local/miniforge3/bin/hf whoami
```

---

## 6. Node.js and npx

Required for the Brave Search MCP server, which is installed and run on-demand via `npx`.
Node.js is pre-installed on the DGX Spark via the system package manager.

```bash
node --version    # v18.19.1
npm --version     # 9.2.0
npx --version     # 9.2.0
```

If missing:

```bash
sudo apt-get install -y nodejs npm
```

---

## 7. mcp-proxy

Required for the Brave Search MCP server. Bridges stdio-based MCP servers to HTTP so that
Open WebUI (running in Docker) can connect to them.

```bash
/usr/local/miniforge3/bin/pip install mcp-proxy
```

Verify:

```bash
/usr/local/miniforge3/bin/mcp-proxy --version
# mcp-proxy, version 0.12.0
```

---

## Summary Table

| Software | Version (this machine) | Used by | Install method |
|---|---|---|---|
| git | 2.43.0 | llama-server, llama-swap | `apt-get install git` |
| cmake | 3.28.3 | llama-server | `apt-get install cmake` |
| gcc / build-essential | 13.3.0 | llama-server | `apt-get install build-essential` |
| make | 4.3 | llama-swap | `apt-get install make` |
| curl | system | all (downloading installers) | `apt-get install curl` |
| NVIDIA driver | 580.159.03 | llama-server | Pre-installed on DGX Spark |
| CUDA toolkit | 13.0 | llama-server | Pre-installed on DGX Spark |
| Go | 1.22.2 (min 1.25.4 for llama-swap) | llama-swap | `go.dev/dl` |
| Docker | 29.2.1 | openwebui | `get.docker.com` |
| Miniforge / Python 3 | Python 3.13.12 | apex-gateway, mcp-proxy | Miniforge installer |
| hf CLI | 1.20.1 | model downloads | Included with Miniforge |
| Node.js | 18.19.1 | brave-search | `apt-get install nodejs npm` |
| mcp-proxy | 0.12.0 | brave-search | `pip install mcp-proxy` |
