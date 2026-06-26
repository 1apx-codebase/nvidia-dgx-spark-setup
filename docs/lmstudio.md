# LM Studio
## NVIDIA DGX Spark (GB10)

LM Studio is an optional, standalone inference application with its own headless daemon (`llmster`),
model library, and OpenAI-compatible server. It operates independently of llama-swap — the two can
coexist but use different ports and model directories.

- **`init.lmstudio`**: CLI wrapper around the `lms` command — `/home/sysadmin/codebase/bin/init.lmstudio`
- **LM Studio CLI docs:** `https://lmstudio.ai/docs/cli`
- **Daemon:** `llmster` — headless process managed via `lms daemon up/down`
- **Server port:** `:9000` (LM Studio's local inference API)
- **Model dir:** `~/.lmstudio/models/` (separate from llama-swap's `~/codebase/models/`)

---

## Quick Reference

```bash
init.lmstudio daemon up         # start the headless daemon
init.lmstudio daemon status     # check daemon health
init.lmstudio ls                # list all models on disk
init.lmstudio ps                # list models loaded in memory
init.lmstudio load              # interactive: pick model + flags
init.lmstudio unload            # interactive: pick model to unload
init.lmstudio unload --all      # unload all models immediately
init.lmstudio server start      # start the inference API server
init.lmstudio server status     # check server + port
init.lmstudio server stop       # stop the inference API server
init.lmstudio daemon down       # stop the daemon
```

---

## Commands

### Daemon

The `llmster` daemon must be running before any model or server commands work.

```bash
init.lmstudio daemon up       # start llmster
init.lmstudio daemon down     # stop llmster
init.lmstudio daemon status   # show daemon status
init.lmstudio daemon update   # update the llmster binary
init.lmstudio restart         # daemon down → daemon up
```

> **Note:** `daemon up` clears `LD_LIBRARY_PATH` before calling `lms` — required on Linux to
> avoid conflicts with system libraries that interfere with the `llmster` process.

### Models

```bash
init.lmstudio ls                      # list all local models on disk
init.lmstudio ps                      # list models loaded in memory

init.lmstudio load                    # interactive menu
init.lmstudio load publisher/model-name/file.gguf
init.lmstudio load publisher/model \
    --gpu max \
    --context-length 32768 \
    --ttl 3600 \
    --identifier my-model

init.lmstudio unload                  # interactive menu (shows loaded models)
init.lmstudio unload publisher/model
init.lmstudio unload --all            # unload everything
```

**Load flags:**

| Flag | Description |
|---|---|
| `--gpu max\|off\|0.0-1.0` | GPU offload fraction |
| `--context-length N` | Context window size in tokens |
| `--ttl N` | Auto-unload after N idle seconds |
| `--identifier name` | Custom name for the API endpoint |
| `--estimate-only` | Preview VRAM usage without actually loading |

### Import a local GGUF

```bash
init.lmstudio import                  # interactive prompts
init.lmstudio import /path/to/model.gguf
init.lmstudio import /path/to/model.gguf --copy --user-repo publisher/model-name -y
```

**Import flags:**

| Flag | Description |
|---|---|
| `--copy` | Copy file into LM Studio (keep original) |
| `--hard-link` | Hard-link into LM Studio (keep original) |
| `--symbolic-link` | Symlink into LM Studio (keep original) |
| `--user-repo user/repo` | Target namespace — skips the interactive prompt |
| `-y` | Skip all confirmations |
| `--dry-run` | Preview what would happen without making changes |

Default (no flag): **move** the file into LM Studio's models directory.

### Download from Hub

```bash
init.lmstudio download bartowski/gemma-2-9b-it-GGUF
```

### Inference Server

LM Studio's local server provides an OpenAI-compatible API on `:9000`.

```bash
init.lmstudio server start    # start (no-op if already running)
init.lmstudio server stop     # stop
init.lmstudio server status   # show status
```

Test the server:

```bash
curl http://localhost:9000/v1/models | jq '[.data[].id]'

curl http://localhost:9000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"publisher/model-name","messages":[{"role":"user","content":"hello"}],"max_tokens":50}'
```

---

## Typical Workflow

```bash
# 1. Start daemon
init.lmstudio daemon up

# 2. Load a model
init.lmstudio load

# 3. Start the inference server
init.lmstudio server start

# 4. Use the API on :9000

# 5. Stop everything
init.lmstudio server stop
init.lmstudio unload --all
init.lmstudio daemon down
```

---

## Relationship to llama-swap

| | llama-swap | LM Studio |
|---|---|---|
| Port | 8080 | 9000 |
| Model dir | `~/codebase/models/gguf/` | `~/.lmstudio/models/` |
| Model loading | On-demand by llama-swap | Manual via `lms load` |
| Managed by | systemd (`llama-swap.service`) | `lms daemon` (no systemd unit) |
| GPU flags | Custom in `llama-swap.yaml` | Via `lms load --gpu` |

LM Studio is **not** part of the primary stack. llama-swap is the production inference server.
LM Studio is available for experimentation or when a GUI is needed.

---

## Service Manager Script Source

```bash
sudo tee /home/sysadmin/codebase/bin/init.lmstudio > /dev/null << 'EOF'
#!/usr/bin/env bash
# =============================================================================
# init.lmstudio — LM Studio CLI Management Wrapper
# All commands validated against official LM Studio docs (v0.0.47)
# Docs: https://lmstudio.ai/docs/cli
# =============================================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()    { echo -e "${CYAN}[INFO]${RESET}  $*"; }
success() { echo -e "${GREEN}[OK]${RESET}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
error()   { echo -e "${RED}[ERROR]${RESET} $*" >&2; }
die()     { error "$*"; exit 1; }
separator() { echo -e "${CYAN}$(printf '─%.0s' {1..60})${RESET}"; }

require_lms() {
    command -v lms &>/dev/null || die "'lms' not found in PATH. Is LM Studio installed?"
}

# LD_LIBRARY_PATH must be cleared on Linux for daemon up (llmster conflict)
lms_clean() { env -u LD_LIBRARY_PATH lms "$@"; }

usage() {
    echo -e ""
    echo -e "${BOLD}init.lmstudio${RESET} — LM Studio CLI Management Wrapper"
    echo -e "Validated against: lms v0.0.47  |  Docs: https://lmstudio.ai/docs/cli"
    echo -e ""
    echo -e "${BOLD}USAGE${RESET}"
    echo -e "  init.lmstudio <command> [subcommand|options]"
    echo -e ""
    echo -e "${BOLD}DAEMON${RESET}  (manages the headless llmster process)"
    echo -e "  daemon up               Start llmster"
    echo -e "  daemon down             Stop llmster"
    echo -e "  daemon status           Show status"
    echo -e "  daemon update           Update binary"
    echo -e "  restart                 down → up in sequence"
    echo -e ""
    echo -e "${BOLD}MODELS${RESET}"
    echo -e "  ls | list               List all models on disk"
    echo -e "  ps                      List models loaded in memory"
    echo -e "  load  <model-key>       Load a model  (interactive if no key given)"
    echo -e "    --gpu max|off|0.0-1.0   GPU offload fraction"
    echo -e "    --context-length <N>    Context window size"
    echo -e "    --ttl <seconds>         Auto-unload after N idle seconds"
    echo -e "    --identifier <name>     Assign a custom API identifier"
    echo -e "    --estimate-only         Preview VRAM usage without loading"
    echo -e "  unload <model-key>      Unload a specific model"
    echo -e "  unload --all            Unload all loaded models"
    echo -e "  import <path>           Import a local .gguf into LM Studio"
    echo -e "    --copy | --hard-link | --symbolic-link"
    echo -e "    --user-repo <u/r>       Set target namespace"
    echo -e "    -y | --dry-run"
    echo -e "  download <model-id>     Download a model from LM Studio Hub"
    echo -e ""
    echo -e "${BOLD}SERVER${RESET}  (local inference API on :9000)"
    echo -e "  server start            Start server (skips if already running)"
    echo -e "  server stop             Stop the inference server"
    echo -e "  server status           Show server status"
    echo -e ""
}

cmd_daemon() {
    local subcmd="${1:-}"; shift || true
    case "$subcmd" in
        up)
            info "Starting llmster daemon (LD_LIBRARY_PATH cleared)…"
            lms_clean daemon up "$@" && success "Daemon started." || die "Failed to start daemon."
            separator; cmd_daemon status ;;
        down)
            info "Stopping llmster daemon…"
            lms daemon down "$@" && success "Daemon stopped." || die "Failed to stop daemon." ;;
        status)
            info "LMS daemon status:"; separator
            lms daemon status "$@" || true; separator ;;
        update)
            info "Updating LMS daemon…"
            lms daemon update "$@" && success "Daemon updated." || die "Daemon update failed." ;;
        "")  error "Missing subcommand. Use: up | down | status | update"; usage; exit 1 ;;
        *)   die "Unknown daemon subcommand: '$subcmd'. Use: up | down | status | update" ;;
    esac
}

cmd_ls() {
    info "Models available on disk:"; separator
    lms ls "$@" || die "lms ls failed. Is the daemon running?"; separator
}

cmd_ps() {
    info "Models currently loaded in memory:"; separator
    lms ps "$@" || die "lms ps failed. Is the daemon running?"; separator
}

# Interactive numbered-menu picker. Sets global PICK_RESULT.
pick_from_list() {
    local prompt="$1"; shift
    local items=("$@"); local count=${#items[@]}
    [[ $count -eq 0 ]] && { error "No items available."; return 1; }
    local cancel_num=$(( count + 1 ))
    echo ""; local i=1
    for item in "${items[@]}"; do
        printf "  ${CYAN}%2d)${RESET} %s\n" "$i" "$item"; (( i++ ))
    done
    printf "  ${RED}%2d)${RESET} Cancel\n" "$cancel_num"; echo ""
    local choice
    while true; do
        read -rp "$(echo -e "${BOLD}${prompt}${RESET} [1-${cancel_num}]: ")" choice
        if [[ "$choice" =~ ^[0-9]+$ ]]; then
            (( choice == cancel_num )) && { info "Cancelled."; return 1; }
            (( choice >= 1 && choice <= count )) && { PICK_RESULT="${items[$((choice-1))]}"; return 0; }
        fi
        warn "Enter a number between 1 and ${cancel_num}."
    done
}

LMS_API_PORT="${LMS_API_PORT:-9000}"
LMS_API_BASE="http://localhost:${LMS_API_PORT}/api/v0"

get_api_models() {
    local state_filter="${1:-}"; local response
    response=$(curl -sf --max-time 3 "${LMS_API_BASE}/models" 2>/dev/null) || return 1
    jq -r --arg s "$state_filter" \
        '.data[] | select(.type == "llm") | select($s == "" or .state == $s) | .id' \
        <<<"$response" 2>/dev/null | sort -u
}

get_local_model_keys() {
    local keys
    keys=$(get_api_models "") && [[ -n "$keys" ]] && { echo "$keys"; return; }
    lms ls 2>/dev/null | awk 'NF >= 1 { print $1 }' | grep '/' | sort -u
}

get_loaded_model_keys() {
    local keys
    keys=$(get_api_models "loaded") && [[ -n "$keys" ]] && { echo "$keys"; return; }
    lms ps 2>/dev/null | grep -i 'identifier:' | awk '{print $NF}' | sort -u
}

cmd_load() {
    local model_key="${1:-}"
    if [[ -z "$model_key" ]]; then
        info "Fetching available models…"
        mapfile -t model_list < <(get_local_model_keys)
        [[ ${#model_list[@]} -eq 0 ]] && die "No local models found. Run 'init.lmstudio download <model-id>' first."
        separator; pick_from_list "Select model to load" "${model_list[@]}" || return 0
        model_key="$PICK_RESULT"
        echo ""; info "GPU offload  (Enter to skip)"
        echo -e "  ${CYAN}1)${RESET} max  ${CYAN}2)${RESET} off  ${CYAN}3)${RESET} 0–1 fraction  ${CYAN}4)${RESET} skip"; echo ""
        local gpu_flag=""; read -rp "$(echo -e "${BOLD}GPU option${RESET} [1-4, default 4]: ")" gpu_choice
        case "${gpu_choice:-4}" in
            1) gpu_flag="--gpu max" ;; 2) gpu_flag="--gpu off" ;;
            3) read -rp "$(echo -e "${BOLD}Fraction${RESET} (0.0–1.0): ")" frac; gpu_flag="--gpu ${frac}" ;;
        esac
        echo ""; local ctx_flag=""
        read -rp "$(echo -e "${BOLD}Context length${RESET} (tokens, Enter to skip): ")" ctx
        [[ -n "$ctx" ]] && ctx_flag="--context-length ${ctx}"
        echo ""; local ttl_flag=""
        read -rp "$(echo -e "${BOLD}Auto-unload TTL${RESET} (idle seconds, Enter to skip): ")" ttl
        [[ -n "$ttl" ]] && ttl_flag="--ttl ${ttl}"
        echo ""; local id_flag=""
        read -rp "$(echo -e "${BOLD}Custom API identifier${RESET} (Enter to skip): ")" ident
        [[ -n "$ident" ]] && id_flag="--identifier ${ident}"
        echo ""; local est_flag=""
        read -rp "$(echo -e "${BOLD}Estimate VRAM only, don't load?${RESET} [y/N]: ")" est
        [[ "${est,,}" == "y" ]] && est_flag="--estimate-only"
        # shellcheck disable=SC2086
        local cmd_args=("$model_key")
        for flag in $gpu_flag $ctx_flag $ttl_flag $id_flag $est_flag; do cmd_args+=("$flag"); done
        separator; info "Running: lms load ${cmd_args[*]}"; separator
        lms load "${cmd_args[@]}" && success "Model loaded: $model_key" || die "Failed to load: $model_key"
    else
        shift; info "Loading model: ${BOLD}${model_key}${RESET}"
        lms load "$model_key" "$@" && success "Loaded: $model_key" || die "Failed to load: $model_key"
    fi
}

cmd_unload() {
    local target="${1:-}"
    if [[ -z "$target" ]]; then
        info "Fetching loaded models…"
        mapfile -t loaded_list < <(get_loaded_model_keys)
        [[ ${#loaded_list[@]} -eq 0 ]] && { warn "No models currently loaded."; return 0; }
        local menu_items=("── Unload ALL models ──" "${loaded_list[@]}")
        separator; pick_from_list "Select model to unload" "${menu_items[@]}" || return 0
        local chosen="$PICK_RESULT"
        if [[ "$chosen" == "── Unload ALL models ──" ]]; then
            read -rp "$(echo -e "${YELLOW}Unload ALL models? [y/N]:${RESET} ")" confirm
            [[ "${confirm,,}" != "y" ]] && { info "Aborted."; return 0; }
            lms unload --all && success "All models unloaded." || die "Failed to unload all."
        else
            separator; info "Unloading: ${BOLD}${chosen}${RESET}"
            lms unload "$chosen" && success "Unloaded: $chosen" || die "Failed to unload: $chosen"
        fi
    elif [[ "$target" == "--all" ]]; then
        info "Unloading all…"; lms unload --all && success "All unloaded." || die "Failed."
    else
        info "Unloading: ${BOLD}${target}${RESET}"
        lms unload "$target" && success "Unloaded: $target" || die "Failed to unload: $target"
    fi
}

cmd_import() {
    local model_path="${1:-}"
    if [[ -z "$model_path" ]]; then
        echo ""; info "Import a local model file into LM Studio  (lms import)"; separator
        while true; do
            read -rp "$(echo -e "${BOLD}Path to .gguf file${RESET}: ")" model_path
            model_path="${model_path/#\~/$HOME}"; [[ -f "$model_path" ]] && break
            warn "File not found: $model_path — try again."
        done
        echo ""; info "File handling mode:"
        echo -e "  ${CYAN}1)${RESET} move  ${CYAN}2)${RESET} --copy  ${CYAN}3)${RESET} --hard-link  ${CYAN}4)${RESET} --symbolic-link"; echo ""
        local file_flag=""; read -rp "$(echo -e "${BOLD}File handling${RESET} [1-4, default 1]: ")" fh
        case "${fh:-1}" in 1) file_flag="" ;; 2) file_flag="--copy" ;; 3) file_flag="--hard-link" ;; 4) file_flag="--symbolic-link" ;; esac
        echo ""; local repo_flag=""
        read -rp "$(echo -e "${BOLD}Target namespace${RESET} (user/repo, Enter to be prompted by lms): ")" repo
        [[ -n "$repo" ]] && repo_flag="--user-repo ${repo}"
        echo ""; local yes_flag=""
        read -rp "$(echo -e "${BOLD}Skip lms confirmations?${RESET} [y/N]: ")" skip_confirm
        [[ "${skip_confirm,,}" == "y" ]] && yes_flag="-y"
        echo ""; local dry_flag=""
        read -rp "$(echo -e "${BOLD}Dry run only?${RESET} [y/N]: ")" dry
        [[ "${dry,,}" == "y" ]] && dry_flag="--dry-run"
        # shellcheck disable=SC2086
        local cmd_args=("$model_path")
        for flag in $file_flag $repo_flag $yes_flag $dry_flag; do cmd_args+=("$flag"); done
        separator; info "Running: lms import ${cmd_args[*]}"; separator
        lms import "${cmd_args[@]}" && success "Imported: $model_path" || die "Failed to import: $model_path"
    else
        [[ ! -e "$model_path" ]] && die "File not found: $model_path"; shift
        info "Importing: ${BOLD}${model_path}${RESET}"
        lms import "$model_path" "$@" && success "Imported: $model_path" || die "Failed to import: $model_path"
    fi
}

cmd_download() {
    local model_id="${1:-}"
    [[ -z "$model_id" ]] && die "Usage: init.lmstudio download <model-id>"
    shift; info "Downloading: ${BOLD}${model_id}${RESET}"
    warn "This may take a while depending on model size."
    separator
    lms get "$model_id" "$@" && success "Download complete: $model_id" || die "Failed: $model_id"
}

server_is_running() { lms server status 2>/dev/null | grep -qi "running"; }

cmd_server() {
    local subcmd="${1:-}"; shift || true
    case "$subcmd" in
        start)
            info "Checking server status…"
            if server_is_running; then
                success "Server is already running."
                separator; lms server status || true; separator
            else
                info "Starting server…"
                lms server start "$@" && success "Server started." || die "Failed to start server."
                separator; lms server status || true; separator
            fi ;;
        stop)
            info "Stopping server…"
            lms server stop "$@" && success "Server stopped." || die "Failed to stop server." ;;
        status)
            info "LM Studio server status:"; separator
            lms server status "$@" || true; separator ;;
        "") error "Missing subcommand. Use: start | stop | status"; usage; exit 1 ;;
        *) die "Unknown server subcommand: '$subcmd'. Use: start | stop | status" ;;
    esac
}

cmd_restart() {
    info "Restarting LMS daemon…"
    cmd_daemon down || true; sleep 2; cmd_daemon up
}

main() {
    require_lms
    local command="${1:-help}"; shift || true
    case "$command" in
        daemon)         cmd_daemon   "$@" ;;
        ls|list)        cmd_ls       "$@" ;;
        ps)             cmd_ps       "$@" ;;
        load)           cmd_load     "$@" ;;
        unload)         cmd_unload   "$@" ;;
        import)         cmd_import   "$@" ;;
        download|get)   cmd_download "$@" ;;
        server)         cmd_server   "$@" ;;
        restart)        cmd_restart  "$@" ;;
        help|--help|-h) usage ;;
        *) error "Unknown command: '$command'"; usage; exit 1 ;;
    esac
}
main "$@"
EOF
sudo chmod 755 /home/sysadmin/codebase/bin/init.lmstudio
```
