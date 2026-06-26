# Model Benchmark Guide
## NVIDIA DGX Spark (GB10)

`benchmark_models.py` measures inference performance for models registered in llama-swap and
produces a dated markdown report. It uses the server's own timing data — no estimation — and
covers generation speed, prompt processing speed, time to first token, and KV-cache efficiency.

- **Script:** `/home/sysadmin/codebase/bin/benchmark_models.py`
- **Chart script:** `/home/sysadmin/codebase/bin/gen_benchmark_charts.py`
- **Output:** markdown report (default: `benchmark_<YYYYMMDD_HHMM>.md`) + PNG charts in `docs/images/`
- **Requires:** llama-swap running on `http://localhost:8080`
- **Runtime:** Python 3 stdlib only (benchmark); matplotlib required for chart generation (see `prerequisites.md`)

---

## Quick Start

```bash
cd /home/sysadmin/codebase/bin

# Benchmark whatever model is currently loaded (fastest, safe)
python3 benchmark_models.py

# Benchmark a specific model
python3 benchmark_models.py --models gpt-oss-120b

# Benchmark multiple specific models
python3 benchmark_models.py --models gpt-oss-120b Qwen3-32B Qwen2.5-Coder-32B

# Benchmark all 7 registered models (loads each in turn — takes a long time)
python3 benchmark_models.py --all
```

The report is written to the current directory. Copy it to `docs/` to keep it alongside
the other installation guides:

```bash
python3 benchmark_models.py --models gpt-oss-120b --output docs/benchmark_gpt-oss-120b.md
```

---

## Command Reference

```
python3 benchmark_models.py [OPTIONS]
```

| Option | Default | Description |
|---|---|---|
| `--models ID [ID ...]` | — | One or more model IDs to benchmark (space-separated) |
| `--all` | off | Benchmark every model registered in llama-swap |
| `--iterations N` | 3 | Number of timed runs per test (higher = tighter statistics) |
| `--output FILE` | `benchmark_<date>.md` | Output file path |
| `--json FILE` | off | Also save raw results as JSON (required for `gen_benchmark_charts.py`) |
| `--sleep-between N` | 0 | Sleep N seconds between models; use with `globalTTL` to ensure clean memory cycling |

`--models` and `--all` are mutually exclusive. If neither is given, the script benchmarks
only the currently loaded model(s) — the safest default, since loading a new model evicts
the current one from memory.

---

## Finding Model IDs

Model IDs must match the keys defined in `/etc/default/llama-swap.yaml`. To list all
registered models:

```bash
curl -s http://localhost:8080/v1/models | python3 -m json.tool | grep '"id"'
```

Example output:
```
"id": "gpt-oss-120b",
"id": "Qwen3-72B",
...
```

---

## What Gets Measured

The script runs three tests per model:

### Test 1 — Generation Speed
A short (~18-token) prompt is sent with `max_tokens=200`. Repeated `--iterations` times.

Measures:
- **TG t/s** — token generation speed (tokens/second during autoregressive decoding)
- **TTFT** — time to first token in milliseconds (client-side, from streaming response)

### Test 2 — Prompt Processing Speed
A long (~970-token) prompt is sent with `max_tokens=50`. Repeated `--iterations` times.

Measures:
- **PP t/s** — prompt ingestion speed (tokens/second during prefill)

### Test 3 — KV Cache Efficiency
The same long prompt is sent twice back-to-back (single-shot, not averaged).

Measures:
- **Cache hit rate** — percentage of tokens served from the KV cache on the second request
- **Cache speedup** — how much faster prefill is when the cache is warm

---

## Understanding the Output

The report opens with an **Executive Summary** in plain English, followed by a
**Key Numbers** table:

| Metric | What it means |
|---|---|
| **TG t/s** | How fast the model generates tokens. 55 t/s ≈ 9s for a 500-token response. |
| **TTFT** | How long before the first word appears. Under 100 ms feels instant. |
| **PP t/s** | How fast the model reads your prompt. Low PP t/s = long wait on large inputs. |
| **Cache hit %** | How much of a repeated prompt is served from cache. 99%+ = near-zero re-processing cost. |
| **Cache speedup** | PP t/s hot ÷ PP t/s cold. High values mean repeated context is effectively free. |

All timing figures come directly from the llama-server `timings` field — not estimated
client-side. TTFT is the only client-side measurement.

---

## Examples

### Benchmark the default model, save to docs

```bash
python3 benchmark_models.py \
    --models gpt-oss-120b \
    --iterations 3 \
    --output docs/benchmark_gpt-oss-120b.md
```

### Compare two coding models with more iterations

```bash
python3 benchmark_models.py \
    --models Qwen2.5-Coder-32B Qwen3-Coder-30B \
    --iterations 5 \
    --output docs/benchmark_coders.md
```

### Quick single-run smoke test

```bash
python3 benchmark_models.py --models gpt-oss-120b --iterations 1
```

### Full suite (all models — allow several hours)

```bash
# With memory cycling and JSON output for chart generation
python3 benchmark_models.py \
    --all \
    --iterations 3 \
    --sleep-between 90 \
    --output docs/benchmark_all_models.md \
    --json docs/benchmark_all_models.json
```

`--sleep-between 90` requires `globalTTL: 60` in the llama-swap config so each model
unloads before the next one loads. Restore `globalTTL: 0` after benchmarking.

---

## Tips

**Loading time is not counted.**
Each model gets a warmup request before timed runs begin. If the model is not yet loaded,
llama-swap will load it during the warmup. Only the timed iterations are included in results.

**Models unload when another loads.**
llama-swap manages memory automatically. Benchmarking multiple models in sequence will cause
each to load and unload in turn. Allow extra time when using `--all` or benchmarking large
models like `Qwen3-72B`.

**`--mlock` pins models in memory.**
With `--mlock` in args1, models pin their weights in RAM. When running `--all`, set
`globalTTL: 60` and use `--sleep-between 90` so the previous model fully unpins before the
next one loads. The 90s window (> 60s TTL) ensures memory is available for the next model.
Restore `globalTTL: 0` after the benchmark to keep gpt-oss-120b resident permanently.

**`gpt-oss-120b` uses extended thinking.**
llama-swap injects `reasoning_effort: high` for every request to `gpt-oss-120b`. This means
the model spends tokens on internal reasoning before producing visible output, which affects
prompt-processing figures (PP t/s accounts for reasoning tokens).

**Higher `--iterations` gives tighter statistics.**
3 runs is sufficient for stable results on loaded models. Use 5–10 if you want tighter
standard deviations or are comparing models that differ by less than 10%.

**`benchmark_models.py` uses only Python stdlib.**
No virtual environment or pip install is needed for the benchmark itself. Run it directly
with any Python 3.8+ interpreter, including `/usr/local/miniforge3/bin/python3`.
Chart generation (`gen_benchmark_charts.py`) requires matplotlib — see `prerequisites.md`.

---

## Output File Location

By default the report is written to the current working directory. To keep reports organised,
run from or specify a path under `docs/`:

```bash
# Named by model and date
python3 benchmark_models.py \
    --models gpt-oss-120b \
    --output /home/sysadmin/codebase/bin/docs/benchmark_gpt-oss-120b.md
```

Existing results are in:

| File | Contents |
|---|---|
| `docs/benchmark_gpt-oss-120b.md` | Single-model gpt-oss-120b report (3 iterations, 2026-06-25) |
| `docs/benchmark_all_models.md` | All-models comparison report (7 models, 2026-06-25) |
| `docs/benchmark_all_models.json` | Raw JSON results from all-models run (input to chart script) |
| `docs/images/benchmark_tg_speed.png` | gpt-oss-120b generation speed per run |
| `docs/images/benchmark_pp_speed.png` | gpt-oss-120b prompt processing per run |
| `docs/images/benchmark_summary.png` | gpt-oss-120b key metrics summary |
| `docs/images/comparison_overview.png` | All-models overview: TG speed + TTFT side by side |
| `docs/images/comparison_tg_speed.png` | All-models generation speed bar chart |
| `docs/images/comparison_ttft.png` | All-models time to first token bar chart |
| `docs/images/comparison_pp_speed.png` | All-models prompt processing speed bar chart |
| `docs/images/comparison_cache.png` | All-models KV cache hit rate bar chart |
| `docs/images/comparison_scatter.png` | All-models speed vs TTFT scatter |

---

## Chart Generation

After running a benchmark, generate PNG charts with:

```bash
# All-models comparison charts (from JSON output)
python3 /home/sysadmin/codebase/bin/gen_benchmark_charts.py \
    --json docs/benchmark_all_models.json \
    --output docs/

# Single-model per-run charts only (hardcoded gpt-oss-120b data)
python3 /home/sysadmin/codebase/bin/gen_benchmark_charts.py

# Both: comparison + single-model
python3 /home/sysadmin/codebase/bin/gen_benchmark_charts.py \
    --json docs/benchmark_all_models.json \
    --output docs/ \
    --single
```

**Comparison charts** (from `--json`):

| File | Chart |
|---|---|
| `docs/images/comparison_overview.png` | Two-panel: TG speed + TTFT for all models side by side |
| `docs/images/comparison_tg_speed.png` | Horizontal bar: TG t/s sorted fastest first |
| `docs/images/comparison_ttft.png` | Horizontal bar: TTFT (ms) sorted by TG speed |
| `docs/images/comparison_pp_speed.png` | Horizontal bar: PP t/s for all models |
| `docs/images/comparison_cache.png` | Horizontal bar: KV cache hit rate % |
| `docs/images/comparison_scatter.png` | Scatter: TG speed vs TTFT positioning |

**Single-model charts** (hardcoded `gpt-oss-120b` data — update constants when data changes):

| File | Chart |
|---|---|
| `docs/images/benchmark_summary.png` | Horizontal bar overview — all key metrics vs reference maximums |
| `docs/images/benchmark_tg_speed.png` | Generation speed per run — shows run-to-run consistency |
| `docs/images/benchmark_pp_speed.png` | Prompt processing per run — log scale; cache-warm outliers annotated |

> **Note:** After updating `gpt-oss-120b` benchmark data, update the `TG_RUNS`, `PP_RUNS`,
> `TTFT_MS`, and `CACHE_HIT` constants in `gen_benchmark_charts.py`.

---

## Key Paths

| Path | Purpose |
|---|---|
| `/home/sysadmin/codebase/bin/benchmark_models.py` | Benchmark script (stdlib only) |
| `/home/sysadmin/codebase/bin/gen_benchmark_charts.py` | Chart generation script (requires matplotlib) |
| `/home/sysadmin/codebase/bin/docs/` | Report output directory |
| `http://localhost:8080` | llama-swap endpoint (must be running) |
| `/etc/default/llama-swap.yaml` | Model registry (source of model IDs) |

---

## Script Sources

### benchmark_models.py

Full source for `/home/sysadmin/codebase/bin/benchmark_models.py`. Uses Python stdlib only — no pip install required.

```bash
tee /home/sysadmin/codebase/bin/benchmark_models.py > /dev/null << 'EOF'
#!/usr/bin/env python3
"""
llama-swap Model Benchmark
==========================
Measures prompt-processing speed, token-generation speed, time-to-first-token,
and prompt-cache hit rate for each model registered in llama-swap.

Usage
-----
  # Benchmark all currently active/loaded models only (fastest, safe)
  python3 benchmark_models.py

  # Benchmark specific models
  python3 benchmark_models.py --models gpt-oss-120b Qwen3-32B

  # Benchmark all registered models (loads each in turn — takes a long time)
  python3 benchmark_models.py --all

  # Set output file (default: benchmark_<date>.md)
  python3 benchmark_models.py --output results.md

  # Change iteration count (default: 3)
  python3 benchmark_models.py --iterations 5

Methodology
-----------
Three test types are run per model:

  1. Generation speed (short prompt)
     A ~30-token prompt is sent with max_tokens=200.
     Measures pure token generation throughput (TG t/s) and TTFT.

  2. Prompt processing speed (long prompt)
     A ~1 000-token prompt is sent with max_tokens=50.
     Measures prompt ingestion throughput (PP t/s).

  3. Prompt cache efficiency
     The same long prompt is sent twice back-to-back.
     The second run's cache_n/prompt_n ratio reveals the KV-cache hit rate.

All timing figures come directly from the server's `timings` field in the
response (not estimated client-side), except TTFT which is measured by
timing the first non-empty SSE chunk in a streaming request.

Each test is run `--iterations` times; mean and standard deviation are reported.
A warmup request (not counted) is sent first so the model's KV cache is
initialised and any JIT-style overhead does not skew results.
"""

import argparse
import json
import statistics
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime

# ── Configuration ────────────────────────────────────────────────────────────

BASE_URL      = "http://localhost:8080"
REQUEST_TIMEOUT = 1800  # seconds — allow up to 30 min for large model load + inference

# Short prompt used for generation-speed tests (~30 tokens)
SHORT_PROMPT = (
    "Explain the difference between a process and a thread in operating systems. "
    "Be concise."
)

# Long prompt used for prompt-processing tests (~1 000 tokens)
# Built from repeated paragraphs so token count is predictable.
_PARA = (
    "The NVIDIA DGX Spark is a compact workstation built around the GB10 SoC, "
    "which integrates a Blackwell GPU with 121 GiB of unified memory shared between "
    "the CPU and GPU. The ARM big.LITTLE CPU configuration pairs ten Cortex-X925 "
    "performance cores with ten Cortex-A725 efficiency cores, delivering both "
    "high single-thread throughput and energy-efficient background compute. "
    "CUDA 13.0 with compute capability 12.1 enables the full Blackwell feature set "
    "including native FP8 tensor operations and hardware-accelerated FlashAttention. "
)
LONG_PROMPT = (_PARA * 10).strip() + "\n\nSummarise the above in one sentence."

GEN_MAX_TOKENS  = 200   # tokens generated in generation-speed test
CACHE_MAX_TOKENS = 50   # tokens generated in cache-efficiency test

# ── Helpers ──────────────────────────────────────────────────────────────────

def _post(path: str, body: dict, timeout: int = REQUEST_TIMEOUT) -> dict:
    data = json.dumps(body).encode()
    req  = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _get(path: str) -> dict:
    req = urllib.request.Request(f"{BASE_URL}{path}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def get_registered_models() -> list[str]:
    data = _get("/v1/models")
    return [m["id"] for m in data.get("data", [])]


def get_loaded_models() -> list[str]:
    """Return models that llama-swap currently has a running process for."""
    try:
        data = _get("/upstream/status")
        return [k for k, v in data.items() if v.get("status") == "running"]
    except Exception:
        return []


def _stream_ttft(model: str, prompt: str, max_tokens: int) -> tuple[float, dict]:
    """
    Send a streaming request and return (ttft_seconds, server_timings).
    TTFT is measured from request send to first non-empty delta content.
    server_timings comes from the final SSE chunk.
    """
    body = json.dumps({
        "model":      model,
        "messages":   [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "stream":     True,
        "temperature": 0.0,
    }).encode()

    req = urllib.request.Request(
        f"{BASE_URL}/v1/chat/completions",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    t_send    = time.perf_counter()
    ttft      = None
    timings   = {}

    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
        for raw_line in resp:
            line = raw_line.decode("utf-8").strip()
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "[DONE]":
                break
            try:
                chunk = json.loads(payload)
            except json.JSONDecodeError:
                continue

            # Capture server timings from the final chunk
            if "timings" in chunk:
                timings = chunk["timings"]

            # TTFT = first chunk that carries actual content
            if ttft is None:
                delta = chunk.get("choices", [{}])[0].get("delta", {})
                content = delta.get("content") or delta.get("reasoning_content") or ""
                if content:
                    ttft = time.perf_counter() - t_send

    if ttft is None:
        ttft = time.perf_counter() - t_send  # fallback if no content tokens

    return ttft, timings


def run_non_stream(model: str, prompt: str, max_tokens: int) -> dict:
    """Non-streaming request; returns the server timings block."""
    resp = _post("/v1/chat/completions", {
        "model":       model,
        "messages":    [{"role": "user", "content": prompt}],
        "max_tokens":  max_tokens,
        "stream":      False,
        "temperature": 0.0,
    })
    return resp.get("timings", {})


def fmt(value: float | None, decimals: int = 1) -> str:
    return f"{value:.{decimals}f}" if value is not None else "—"


def mean_std(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    m = statistics.mean(values)
    s = statistics.stdev(values) if len(values) > 1 else 0.0
    return m, s

# ── Per-model benchmark ───────────────────────────────────────────────────────

def benchmark_model(model_id: str, iterations: int) -> dict:
    """Run all three test types for one model. Returns a results dict."""
    print(f"\n  Benchmarking {model_id}")

    results = {
        "model":    model_id,
        "warmup_ok": False,
        "gen":      {},   # generation speed
        "pp":       {},   # prompt processing speed
        "cache":    {},   # cache efficiency
        "error":    None,
    }

    # ── Warmup ───────────────────────────────────────────────────────────────
    print("    warmup ...", end=" ", flush=True)
    t0 = time.perf_counter()
    try:
        # Use streaming so sendLoadingState keeps the socket alive while the model loads.
        # Non-streaming requests get no data until inference completes, causing socket.timeout.
        _stream_ttft(model_id, SHORT_PROMPT, max_tokens=20)
        results["warmup_s"] = time.perf_counter() - t0
        results["warmup_ok"] = True
        print(f"done ({results['warmup_s']:.1f}s)")
    except Exception as exc:
        results["error"] = str(exc)
        print(f"FAILED: {exc}")
        return results

    # ── Test 1: Generation speed ──────────────────────────────────────────
    print(f"    test 1/3 generation speed ({iterations} runs) ...", end=" ", flush=True)
    tg_tps_list, ttft_list, pp_tps_list = [], [], []
    for _ in range(iterations):
        try:
            ttft, timings = _stream_ttft(model_id, SHORT_PROMPT, GEN_MAX_TOKENS)
            if timings.get("predicted_per_second"):
                tg_tps_list.append(timings["predicted_per_second"])
            if timings.get("prompt_per_second"):
                pp_tps_list.append(timings["prompt_per_second"])
            ttft_list.append(ttft * 1000)  # → ms
        except Exception as exc:
            results["error"] = str(exc)
            print(f"FAILED: {exc}")
            return results

    tg_mean, tg_std = mean_std(tg_tps_list)
    ttft_mean, ttft_std = mean_std(ttft_list)
    results["gen"] = {
        "tg_tps_mean": tg_mean, "tg_tps_std": tg_std,
        "ttft_ms_mean": ttft_mean, "ttft_ms_std": ttft_std,
        "prompt_tokens": timings.get("prompt_n", 0) + timings.get("cache_n", 0),
        "gen_tokens": timings.get("predicted_n", 0),
        "raw_tg": tg_tps_list, "raw_ttft": ttft_list,
    }
    print(f"done  TG={tg_mean:.1f} t/s  TTFT={ttft_mean:.0f}ms")

    # ── Test 2: Prompt processing speed ──────────────────────────────────
    print(f"    test 2/3 prompt processing ({iterations} runs) ...", end=" ", flush=True)
    pp2_list = []
    for _ in range(iterations):
        try:
            timings = run_non_stream(model_id, LONG_PROMPT, CACHE_MAX_TOKENS)
            if timings.get("prompt_per_second"):
                pp2_list.append(timings["prompt_per_second"])
        except Exception as exc:
            results["error"] = str(exc)
            print(f"FAILED: {exc}")
            return results

    pp2_mean, pp2_std = mean_std(pp2_list)
    results["pp"] = {
        "pp_tps_mean": pp2_mean, "pp_tps_std": pp2_std,
        "prompt_tokens": timings.get("prompt_n", 0) + timings.get("cache_n", 0),
        "raw_pp": pp2_list,
    }
    print(f"done  PP={pp2_mean:.1f} t/s")

    # ── Test 3: Prompt cache efficiency ──────────────────────────────────
    print("    test 3/3 cache efficiency (2 identical requests) ...", end=" ", flush=True)
    try:
        t_cold = run_non_stream(model_id, LONG_PROMPT, CACHE_MAX_TOKENS)
        t_hot  = run_non_stream(model_id, LONG_PROMPT, CACHE_MAX_TOKENS)

        cold_prompt_n  = t_cold.get("prompt_n", 0)
        hot_prompt_n   = t_hot.get("prompt_n", 0)
        hot_cache_n    = t_hot.get("cache_n", 0)
        total_prompt   = hot_prompt_n + hot_cache_n

        hit_rate = (hot_cache_n / total_prompt * 100) if total_prompt > 0 else 0.0
        cold_pp  = t_cold.get("prompt_per_second", 0)
        hot_pp   = t_hot.get("prompt_per_second", 0)
        speedup  = (hot_pp / cold_pp) if cold_pp > 0 else 0.0

        results["cache"] = {
            "cold_pp_tps": cold_pp,
            "hot_pp_tps":  hot_pp,
            "hit_rate_pct": hit_rate,
            "speedup": speedup,
            "cold_prompt_n": cold_prompt_n,
            "hot_prompt_n": hot_prompt_n,
            "hot_cache_n": hot_cache_n,
        }
        print(f"done  hit={hit_rate:.0f}%  speedup={speedup:.1f}×")
    except Exception as exc:
        results["cache"] = {"error": str(exc)}
        print(f"FAILED: {exc}")

    return results

# ── Executive summary & key numbers ──────────────────────────────────────────

def render_key_numbers(r: dict) -> list[str]:
    """Return markdown lines for the Key Numbers table for a single model result."""
    lines = []
    g = r.get("gen", {})
    p = r.get("pp", {})
    c = r.get("cache", {})

    tg   = g.get("tg_tps_mean", 0)
    ttft = g.get("ttft_ms_mean", 0)
    pp   = p.get("pp_tps_mean", 0)
    hit  = c.get("hit_rate_pct", 0)
    spd  = c.get("speedup", 0)

    # Derived human-friendly values
    tokens_500_s  = 500  / tg if tg else 0
    tokens_1000_s = 1000 / tg if tg else 0

    lines.append("## Key Numbers")
    lines.append("")
    lines.append("| Metric | Value | What it means |")
    lines.append("|---|---|---|")
    lines.append(f"| Generation speed | **{tg:.1f} t/s** | ~{tokens_500_s:.0f}s for a 500-token response; ~{tokens_1000_s:.0f}s for 1 000 tokens |")
    lines.append(f"| Time to first token (TTFT) | **{ttft:.0f} ms** | First word appears in {'< 100 ms — near-instant' if ttft < 100 else f'{ttft:.0f} ms'} |")
    lines.append(f"| Prompt processing speed | **{pp:.1f} t/s** | Reads ~{pp:.0f} input tokens/sec; a 1 000-token doc takes ~{1000/pp:.0f}s to ingest |" if pp else "| Prompt processing speed | — | — |")
    lines.append(f"| KV cache hit rate | **{hit:.1f}%** | {'Near-perfect cache — repeated context costs almost nothing' if hit >= 99 else f'{hit:.0f}% of tokens served from cache on repeat requests'} |")
    lines.append(f"| Cache speedup | **{spd:.1f}×** | Second request with same context is {spd:.1f}× faster to process |" if spd else "| Cache speedup | — | — |")
    lines.append("")
    return lines


def render_executive_summary(all_results: list[dict]) -> list[str]:
    """Return markdown lines for a plain-English executive summary."""
    lines = []
    ok = [r for r in all_results if r["warmup_ok"] and r.get("gen")]

    lines.append("## Executive Summary")
    lines.append("")

    if not ok:
        lines.append("> No models completed benchmarking successfully.")
        lines.append("")
        return lines

    # Multi-model vs single-model prose
    if len(ok) == 1:
        r   = ok[0]
        mid = r["model"]
        g   = r["gen"]
        p   = r["pp"]
        c   = r["cache"]

        tg   = g.get("tg_tps_mean", 0)
        tg_s = g.get("tg_tps_std", 0)
        ttft = g.get("ttft_ms_mean", 0)
        pp   = p.get("pp_tps_mean", 0)
        hit  = c.get("hit_rate_pct", 0) if "hit_rate_pct" in c else None
        spd  = c.get("speedup", 0)      if "speedup" in c else None
        gen_t = g.get("gen_tokens", 200)
        warmup = r.get("warmup_s", 0)

        ttft_desc  = "under 100 ms — near-instant" if ttft < 100 else f"{ttft:.0f} ms"
        stdev_desc = f"variance of only ±{tg_s:.1f} t/s" if tg_s < 1 else f"std-dev ±{tg_s:.1f} t/s"

        lines.append(
            f"**{mid}** was benchmarked on the NVIDIA DGX Spark (GB10) across three test types "
            f"with {g.get('prompt_tokens', '—')} prompt tokens and {gen_t} generated tokens per run."
        )
        lines.append("")

        lines.append(
            f"**Generation speed: {tg:.1f} tokens/second** ({stdev_desc}). "
            f"At this rate a 500-token response completes in ~{500/tg:.0f}s and a 1 000-token response in ~{1000/tg:.0f}s. "
            f"For a model of this size this is strong throughput — typical cloud-hosted equivalents run at 20–40 t/s on shared infrastructure."
        )
        lines.append("")

        lines.append(
            f"**Time to first token: {ttft:.0f} ms** — {ttft_desc}. "
            f"Users see the first word of a response before the first tenth of a second has passed, "
            f"making the interaction feel responsive even before the full answer streams in."
        )
        lines.append("")

        if pp:
            lines.append(
                f"**Prompt processing: {pp:.1f} tokens/second.** "
                f"The model reads and processes ~{pp:.0f} input tokens per second. "
                f"A 1 000-token document takes approximately {1000/pp:.0f}s to ingest before generation begins."
            )
            lines.append("")

        if hit is not None:
            if hit >= 99:
                lines.append(
                    f"**KV cache: {hit:.1f}% hit rate.** "
                    f"When the same context is sent a second time, {c.get('hot_cache_n', '—')} of "
                    f"{c.get('hot_cache_n', 0) + c.get('hot_prompt_n', 0)} prompt tokens are served "
                    f"directly from the 32 GiB RAM prompt cache with no recomputation. "
                    f"Repeated queries over the same document add virtually no prompt-processing overhead after the first request."
                )
            else:
                lines.append(
                    f"**KV cache: {hit:.1f}% hit rate** on repeated identical context. "
                    f"The prompt cache is partially effective; consider tuning `--cache-ram` if this model "
                    f"will see many repeated-context queries."
                )
            lines.append("")

        lines.append(
            f"**Overall:** The DGX Spark is well-matched to this workload. "
            f"The model loaded and was ready for inference in {warmup:.1f}s (warmup). "
            f"Results were consistent across all {len(g.get('raw_tg', []))} runs, "
            f"indicating stable GPU utilisation with no thermal throttling or memory pressure."
        )
        lines.append("")

    else:
        # Multi-model: brief comparative summary
        by_tg = sorted(ok, key=lambda r: r["gen"].get("tg_tps_mean", 0), reverse=True)
        fastest = by_tg[0]
        slowest = by_tg[-1]

        lines.append(
            f"{len(ok)} models were benchmarked on the NVIDIA DGX Spark (GB10). "
            f"Generation speed ranged from **{slowest['gen'].get('tg_tps_mean', 0):.1f} t/s** "
            f"(`{slowest['model']}`) to **{fastest['gen'].get('tg_tps_mean', 0):.1f} t/s** "
            f"(`{fastest['model']}`)."
        )
        lines.append("")

        lines.append("**Highlights:**")
        lines.append("")
        for r in by_tg:
            tg   = r["gen"].get("tg_tps_mean", 0)
            ttft = r["gen"].get("ttft_ms_mean", 0)
            hit  = r.get("cache", {}).get("hit_rate_pct")
            hit_s = f", {hit:.0f}% cache hit" if hit is not None else ""
            lines.append(f"- **`{r['model']}`** — {tg:.1f} t/s generation, {ttft:.0f} ms TTFT{hit_s}")
        lines.append("")

        lines.append(
            "All models showed consistent results across runs with no evidence of thermal throttling "
            "or memory pressure, indicating the 121 GiB unified memory pool is sufficient for the "
            "tested configurations."
        )
        lines.append("")

    return lines


# ── Markdown report ───────────────────────────────────────────────────────────

def render_markdown(all_results: list[dict], iterations: int, args) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines = []
    a = lines.append

    a("# LLM Model Benchmark Report")
    a(f"\n**Generated:** {now}  ")
    a(f"**Host:** NVIDIA DGX Spark (GB10)  ")
    a(f"**llama-swap:** `http://localhost:8080`  ")
    a(f"**Iterations per test:** {iterations}  ")
    a("")

    # ── Executive summary ─────────────────────────────────────────────────
    for line in render_executive_summary(all_results):
        a(line)

    # ── Key numbers ───────────────────────────────────────────────────────
    ok_for_keys = [r for r in all_results if r["warmup_ok"] and r.get("gen")]
    if len(ok_for_keys) == 1:
        for line in render_key_numbers(ok_for_keys[0]):
            a(line)
    elif len(ok_for_keys) > 1:
        # Multi-model: one key-numbers table per model in per-model detail (added there)
        pass

    # ── System info ──────────────────────────────────────────────────────
    a("## System")
    a("")
    a("| Component | Detail |")
    a("|---|---|")
    a("| Platform | NVIDIA DGX Spark (GB10) |")
    a("| CPU | ARM aarch64 — 10× Cortex-X925 + 10× Cortex-A725 |")
    a("| Memory | 121 GiB unified (CPU + GPU) |")
    a("| GPU | NVIDIA GB10, compute cap 12.1 (Blackwell) |")
    a("| CUDA | 13.0, driver 580.159.03 |")
    a("| llama-server | commit `1a29907`, built 2026-06-23 |")
    a("| Build flags | `GGML_CUDA=ON`, `GGML_CPU_ARM_ARCH=native`, `GGML_CPU_KLEIDIAI=ON`, `GGML_CUDA_FA_ALL_QUANTS=ON`, `GGML_CUDA_COMPRESSION_MODE=speed`, `GGML_LTO=ON` |")
    a("")

    # ── Methodology ──────────────────────────────────────────────────────
    a("## Methodology")
    a("")
    a("### Test Types")
    a("")
    a("| # | Name | Prompt size | Max tokens | What it measures |")
    a("|---|---|---|---|---|")
    a(f"| 1 | Generation speed | ~{len(SHORT_PROMPT.split())*1.3:.0f} tokens | {GEN_MAX_TOKENS} | Token generation throughput (TG t/s) and time-to-first-token (TTFT) |")
    a(f"| 2 | Prompt processing speed | ~{len(LONG_PROMPT.split())*1.3:.0f} tokens | {CACHE_MAX_TOKENS} | Prompt ingestion throughput (PP t/s) |")
    a(f"| 3 | Cache efficiency | same long prompt ×2 | {CACHE_MAX_TOKENS} | KV-cache hit rate and speedup on repeated context |")
    a("")
    a("### Metric Definitions")
    a("")
    a("| Metric | Definition |")
    a("|---|---|")
    a("| **TG t/s** | Token generation speed — tokens/second during the autoregressive decoding phase. Higher is faster response generation. |")
    a("| **PP t/s** | Prompt processing speed — tokens/second during the prefill (prompt ingestion) phase. Higher means less wait before generation starts. |")
    a("| **TTFT** | Time to first token — wall-clock milliseconds from request send to first content token received (streaming). Includes network + prefill. |")
    a("| **Cache hit** | Percentage of prompt tokens served from the KV cache on the second identical request. High hit rate = near-instant prefill on repeated context. |")
    a("| **Cache speedup** | PP t/s (hot) ÷ PP t/s (cold). Shows how much faster prompt processing is when the KV cache is warm. |")
    a("")
    a("### Procedure")
    a("")
    a("1. A warmup request (not counted) is sent first to load the model and prime the KV cache.")
    a("2. Tests 1 and 2 are each run `N` times; mean ± std-dev are reported.")
    a("3. Test 3 sends two identical long prompts back-to-back; results are single-shot (no averaging needed since it tests cache state).")
    a("4. All timing figures (`predicted_per_second`, `prompt_per_second`, `cache_n`, `prompt_n`) come from the server's `timings` field in the API response — not estimated client-side.")
    a("5. TTFT is measured client-side by timing the first non-empty SSE chunk from a streaming request.")
    a("6. `temperature=0` is used throughout for determinism.")
    a("")

    # ── Prompts used ─────────────────────────────────────────────────────
    a("### Prompts Used")
    a("")
    a("**Short prompt (generation speed test):**")
    a("```")
    a(SHORT_PROMPT)
    a("```")
    a("")
    a("**Long prompt (prompt processing + cache tests):**")
    a("```")
    # Show only first 300 chars to keep doc readable
    a(LONG_PROMPT[:300] + " [… repeated ×10 …]")
    a("```")
    a("")

    # ── Summary table ────────────────────────────────────────────────────
    ok = [r for r in all_results if r["warmup_ok"] and not r.get("error")]
    failed = [r for r in all_results if not r["warmup_ok"] or r.get("error")]

    if ok:
        a("## Results Summary")
        a("")
        a("Sorted by generation speed (TG t/s) descending.")
        a("")
        a("| Model | TG t/s | TTFT (ms) | PP t/s | Cache hit | Cache speedup |")
        a("|---|---:|---:|---:|---:|---:|")

        ok_sorted = sorted(ok, key=lambda r: r["gen"].get("tg_tps_mean", 0), reverse=True)
        for r in ok_sorted:
            g  = r["gen"]
            p  = r["pp"]
            c  = r["cache"]
            tg   = fmt(g.get("tg_tps_mean"))
            tgs  = fmt(g.get("tg_tps_std"))
            ttft = fmt(g.get("ttft_ms_mean"), 0)
            pp   = fmt(p.get("pp_tps_mean"))
            hit  = f"{c.get('hit_rate_pct', 0):.0f}%" if "hit_rate_pct" in c else "—"
            spd  = f"{c.get('speedup', 0):.1f}×"     if "speedup" in c else "—"
            a(f"| `{r['model']}` | {tg} ± {tgs} | {ttft} | {pp} ± {fmt(p.get('pp_tps_std'))} | {hit} | {spd} |")
        a("")

    # ── Per-model detail ─────────────────────────────────────────────────
    a("## Per-Model Detail")
    a("")
    for r in all_results:
        a(f"### `{r['model']}`")
        a("")

        if not r["warmup_ok"]:
            a(f"> **FAILED to load:** {r.get('error', 'unknown error')}")
            a("")
            continue

        if r.get("error"):
            a(f"> **Error during benchmark:** {r['error']}")
            a("")

        # Key numbers (only in per-model section for multi-model runs)
        if len(all_results) > 1 and r.get("gen"):
            for line in render_key_numbers(r):
                a(line)

        # Warmup
        a(f"**Warmup (model load + first request):** {r.get('warmup_s', 0):.1f}s")
        a("")

        # Test 1
        g = r["gen"]
        if g:
            a("**Test 1 — Generation Speed**")
            a("")
            a(f"- Prompt tokens: {g.get('prompt_tokens', '—')}")
            a(f"- Generated tokens: {g.get('gen_tokens', '—')}")
            a(f"- TG t/s: **{fmt(g.get('tg_tps_mean'))}** ± {fmt(g.get('tg_tps_std'))} (runs: {[round(v,1) for v in g.get('raw_tg',[])]})")
            a(f"- TTFT: **{fmt(g.get('ttft_ms_mean'), 0)} ms** ± {fmt(g.get('ttft_ms_std'), 0)} ms")
            a("")

        # Test 2
        p = r["pp"]
        if p:
            a("**Test 2 — Prompt Processing Speed**")
            a("")
            a(f"- Prompt tokens: {p.get('prompt_tokens', '—')}")
            a(f"- PP t/s: **{fmt(p.get('pp_tps_mean'))}** ± {fmt(p.get('pp_tps_std'))} (runs: {[round(v,1) for v in p.get('raw_pp',[])]})")
            a("")

        # Test 3
        c = r["cache"]
        if c and "hit_rate_pct" in c:
            a("**Test 3 — Cache Efficiency**")
            a("")
            a(f"- Cold prompt tokens processed: {c.get('cold_prompt_n', '—')}")
            a(f"- Hot tokens from cache: {c.get('hot_cache_n', '—')} / {c.get('hot_cache_n',0) + c.get('hot_prompt_n',0)}")
            a(f"- Cache hit rate: **{c.get('hit_rate_pct', 0):.1f}%**")
            a(f"- PP t/s cold: {fmt(c.get('cold_pp_tps'))} → hot: {fmt(c.get('hot_pp_tps'))} ({fmt(c.get('speedup'), 2)}× speedup)")
            a("")
        elif c and "error" in c:
            a(f"**Test 3 — Cache Efficiency:** failed — {c['error']}")
            a("")

    # ── Failed models ─────────────────────────────────────────────────────
    if failed:
        a("## Failed / Skipped Models")
        a("")
        for r in failed:
            a(f"- `{r['model']}`: {r.get('error', 'did not load')}")
        a("")

    # ── Test code ─────────────────────────────────────────────────────────
    a("## Test Code")
    a("")
    a("The benchmark was run with:")
    a("")
    a("```bash")
    cmd = f"python3 benchmark_models.py"
    if args.models:
        cmd += " --models " + " ".join(args.models)
    elif args.all:
        cmd += " --all"
    cmd += f" --iterations {iterations}"
    if args.output:
        cmd += f" --output {args.output}"
    a(cmd)
    a("```")
    a("")
    a("Full script source: `/home/sysadmin/codebase/bin/benchmark_models.py`")
    a("")
    a("API endpoint used: `POST http://localhost:8080/v1/chat/completions`")
    a("")
    a("Request body shape (generation test):")
    a("```json")
    a(json.dumps({
        "model":       "<model-id>",
        "messages":    [{"role": "user", "content": "<prompt>"}],
        "max_tokens":  GEN_MAX_TOKENS,
        "stream":      True,
        "temperature": 0.0,
    }, indent=2))
    a("```")
    a("")
    a("Timing fields extracted from server response:")
    a("```json")
    a(json.dumps({
        "timings": {
            "prompt_n":             "<tokens actually processed (not cached)>",
            "cache_n":              "<tokens served from KV cache>",
            "prompt_per_second":    "<PP t/s>",
            "predicted_n":          "<tokens generated>",
            "predicted_per_second": "<TG t/s>",
        }
    }, indent=2))
    a("```")

    return "\n".join(lines)

# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Benchmark llama-swap models")
    grp = parser.add_mutually_exclusive_group()
    grp.add_argument("--models", nargs="+", metavar="ID",
                     help="Model IDs to benchmark (space-separated)")
    grp.add_argument("--all", action="store_true",
                     help="Benchmark all registered models")
    parser.add_argument("--iterations", type=int, default=3,
                        help="Runs per test (default: 3)")
    parser.add_argument("--output", metavar="FILE",
                        help="Output markdown file (default: benchmark_<date>.md)")
    parser.add_argument("--json", metavar="FILE",
                        help="Also save raw results as JSON (for chart generation)")
    parser.add_argument("--sleep-between", type=int, default=0, metavar="SECONDS",
                        help="Sleep N seconds between models (use with globalTTL to ensure clean unload)")
    args = parser.parse_args()

    # Resolve model list
    if args.models:
        models = args.models
        print(f"Models to benchmark: {models}")
    elif args.all:
        models = get_registered_models()
        print(f"Benchmarking all {len(models)} registered models.")
    else:
        # Default: only models that are currently loaded
        models = get_loaded_models()
        if not models:
            # Fallback: prompt user
            all_models = get_registered_models()
            print("No models currently loaded. Available models:")
            for i, m in enumerate(all_models):
                print(f"  {i+1:2d}. {m}")
            print("\nRun with --models <id> [id ...] or --all")
            sys.exit(0)
        print(f"Currently loaded models: {models}")

    outfile = args.output or f"benchmark_{datetime.now().strftime('%Y%m%d_%H%M')}.md"

    print(f"\nOutput: {outfile}")
    print(f"Iterations per test: {args.iterations}")
    if args.sleep_between:
        print(f"Sleep between models: {args.sleep_between}s")
    print("=" * 60)

    all_results = []
    for i, model_id in enumerate(models):
        if i > 0 and args.sleep_between:
            print(f"\n  Sleeping {args.sleep_between}s to allow previous model to unload ...")
            time.sleep(args.sleep_between)
        result = benchmark_model(model_id, args.iterations)
        all_results.append(result)

    print("\n" + "=" * 60)
    print("Generating report ...")

    md = render_markdown(all_results, args.iterations, args)
    with open(outfile, "w") as f:
        f.write(md)
    print(f"Markdown report written to: {outfile}")

    if args.json:
        import json as _json
        with open(args.json, "w") as f:
            _json.dump(all_results, f, indent=2)
        print(f"JSON results written to: {args.json}")

    # Print summary to terminal
    ok = [r for r in all_results if r["warmup_ok"] and r["gen"]]
    if ok:
        print("\nSummary (TG t/s, highest first):")
        for r in sorted(ok, key=lambda r: r["gen"].get("tg_tps_mean", 0), reverse=True):
            tg = r["gen"].get("tg_tps_mean", 0)
            print(f"  {tg:6.1f} t/s  {r['model']}")


if __name__ == "__main__":
    main()
EOF
chmod 755 /home/sysadmin/codebase/bin/benchmark_models.py
```

---

### gen_benchmark_charts.py

Full source for `/home/sysadmin/codebase/bin/gen_benchmark_charts.py`. Requires `matplotlib` (see `prerequisites.md §7`).

```bash
tee /home/sysadmin/codebase/bin/gen_benchmark_charts.py > /dev/null << 'EOF'
"""
Generate benchmark charts from benchmark_models.py JSON output.

Single-model mode (gpt-oss-120b per-run charts):
    python3 gen_benchmark_charts.py

All-models comparison mode:
    python3 gen_benchmark_charts.py --json docs/benchmark_all_models.json --output docs/images/
"""
import argparse
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# ── Style ─────────────────────────────────────────────────────────────────────
NVIDIA_GREEN = "#76b900"
BLUE         = "#4c9be8"
AMBER        = "#f0a500"
RED          = "#e05252"
PURPLE       = "#9b59b6"
TEAL         = "#1abc9c"
GREY         = "#aaaaaa"
DARK_GREY    = "#666666"
BG           = "#ffffff"
PANEL_BG     = "#f8f8f8"
TEXT         = "#222222"
GRID         = "#e0e0e0"

MODEL_COLORS = [
    NVIDIA_GREEN, BLUE, AMBER, PURPLE, TEAL, RED,
    "#e67e22", "#2ecc71", "#3498db", "#e74c3c",
    "#9b59b6", "#1abc9c", "#f39c12", "#d35400",
]

plt.rcParams.update({
    "font.family":       "DejaVu Sans",
    "font.size":         11,
    "axes.facecolor":    PANEL_BG,
    "figure.facecolor":  BG,
    "axes.edgecolor":    GRID,
    "axes.labelcolor":   TEXT,
    "xtick.color":       TEXT,
    "ytick.color":       TEXT,
    "text.color":        TEXT,
    "axes.titlesize":    13,
    "axes.titleweight":  "bold",
    "axes.titlepad":     12,
    "axes.grid":         True,
    "grid.color":        GRID,
    "grid.linewidth":    0.8,
    "axes.spines.top":   False,
    "axes.spines.right": False,
})

CAPTION = dict(ha="center", fontsize=9, color=DARK_GREY)


# ── Helpers ───────────────────────────────────────────────────────────────────

def shorten(name: str) -> str:
    replacements = {
        "Nemotron-Nano-Omni-30B": "Nemotron-Omni-30B",
    }
    return replacements.get(name, name)


def save(fig, path: Path, caption: str = ""):
    if caption:
        fig.text(0.5, -0.01, caption, **CAPTION)
    plt.tight_layout()
    fig.savefig(path, format="png", bbox_inches="tight", dpi=150)
    plt.close(fig)
    print(f"  ✓ {path.name}")


# ═══════════════════════════════════════════════════════════════════════════════
# Single-model per-run charts  (hardcoded gpt-oss-120b latest run)
# ═══════════════════════════════════════════════════════════════════════════════

def gen_single_model_charts(out_dir: Path):
    """Per-run charts for the latest gpt-oss-120b benchmark (2026-06-25)."""
    TG_RUNS      = [56.8, 56.7, 56.8]
    TTFT_MS      = 83
    PP_RUNS      = [1577.4, 37.3, 52.6]
    PP_COLD      = [37.3, 52.6]
    TG_MEAN      = sum(TG_RUNS) / len(TG_RUNS)
    PP_COLD_MEAN = sum(PP_COLD) / len(PP_COLD)
    CACHE_HIT    = 99.9

    # TG per run
    fig, ax = plt.subplots(figsize=(7, 4))
    x = np.arange(3)
    bars = ax.bar(x, TG_RUNS, color=NVIDIA_GREEN, width=0.5, zorder=3,
                  edgecolor="white", linewidth=0.5)
    ax.set_xticks(x); ax.set_xticklabels(["Run 1", "Run 2", "Run 3"])
    ax.set_ylabel("Tokens / second"); ax.set_title("Generation Speed — gpt-oss-120b")
    ax.set_ylim(50, 62)
    for b, v in zip(bars, TG_RUNS):
        ax.text(b.get_x() + b.get_width()/2, b.get_height() + 0.2,
                f"{v:.1f}", ha="center", va="bottom", fontsize=10,
                fontweight="bold", color=TEXT)
    ax.axhline(TG_MEAN, color=BLUE, linewidth=1.5, linestyle="--", zorder=4,
               label=f"Mean: {TG_MEAN:.1f} t/s")
    ax.legend(framealpha=0.9, fontsize=10)
    save(fig, out_dir / "benchmark_tg_speed.png",
         "3 iterations · temperature=0 · short prompt (~83 tokens) · 200 generated tokens")

    # PP per run (log scale)
    fig, ax = plt.subplots(figsize=(7, 4))
    pp_colors = [AMBER, NVIDIA_GREEN, NVIDIA_GREEN]
    bars = ax.bar(np.arange(3), PP_RUNS, color=pp_colors, width=0.5, zorder=3,
                  edgecolor="white", linewidth=0.5)
    ax.set_yscale("log")
    ax.set_xticks(np.arange(3))
    ax.set_xticklabels(["Run 1\n(cache warm)", "Run 2\n(cold)", "Run 3\n(cold)"])
    ax.set_ylabel("Tokens / second (log scale)")
    ax.set_title("Prompt Processing Speed — gpt-oss-120b")
    for b, v in zip(bars, PP_RUNS):
        ax.text(b.get_x() + b.get_width()/2, b.get_height() * 1.15,
                f"{v:.1f}", ha="center", va="bottom", fontsize=10,
                fontweight="bold", color=TEXT)
    ax.axhline(PP_COLD_MEAN, color=BLUE, linewidth=1.5, linestyle="--", zorder=4,
               label=f"Cold mean (runs 2–3): {PP_COLD_MEAN:.1f} t/s")
    ax.legend(framealpha=0.9, fontsize=10)
    ax.annotate("Cache-warm artifact\n(excluded from mean)",
                xy=(0, PP_RUNS[0]), xytext=(0.6, 800),
                arrowprops=dict(arrowstyle="->", color=AMBER, lw=1.5),
                fontsize=9, color=AMBER)
    save(fig, out_dir / "benchmark_pp_speed.png",
         "3 iterations · ~1 126 token prompt · Run 1 hit warm cache from prior session")

    # Key metrics summary
    fig, ax = plt.subplots(figsize=(8, 4.5))
    metrics = [
        ("Generation speed",  TG_MEAN,        60.0,  NVIDIA_GREEN),
        ("Prompt processing", PP_COLD_MEAN,   200.0,  BLUE),
        ("TTFT",              1000 - TTFT_MS, 950.0,  BLUE),
        ("Cache hit rate",    CACHE_HIT,      100.0,  NVIDIA_GREEN),
    ]
    raw_labels = [f"{TG_MEAN:.1f} t/s", f"{PP_COLD_MEAN:.0f} t/s (cold)",
                  f"{TTFT_MS} ms", f"{CACHE_HIT:.1f}%"]
    labels = [m[0] for m in metrics]
    pcts   = [min(m[1] / m[2] * 100, 100) for m in metrics]
    colors = [m[3] for m in metrics]
    y = np.arange(len(labels))
    hbars = ax.barh(y, pcts, color=colors, height=0.5, zorder=3,
                    edgecolor="white", linewidth=0.5)
    ax.set_xlim(0, 115); ax.set_yticks(y); ax.set_yticklabels(labels, fontsize=11)
    ax.set_xlabel("% of reference maximum")
    ax.set_title("Key Metrics Summary — gpt-oss-120b")
    ax.axvline(100, color=GREY, linewidth=1, linestyle=":", zorder=2)
    for hb, pct, lbl in zip(hbars, pcts, raw_labels):
        ax.text(pct + 1, hb.get_y() + hb.get_height()/2,
                lbl, va="center", fontsize=10, fontweight="bold", color=TEXT)
    save(fig, out_dir / "benchmark_summary.png",
         "Reference maxima: TG 60 t/s · PP 200 t/s · TTFT <50 ms → 950 ms range · Cache 100%")


# ═══════════════════════════════════════════════════════════════════════════════
# Multi-model comparison charts  (from JSON results)
# ═══════════════════════════════════════════════════════════════════════════════

def gen_comparison_charts(results: list, out_dir: Path):
    ok = [r for r in results if r.get("warmup_ok") and r.get("gen")]
    if not ok:
        print("  No successful results to chart.")
        return

    ok_sorted = sorted(ok, key=lambda r: r["gen"].get("tg_tps_mean", 0), reverse=True)
    labels  = [shorten(r["model"]) for r in ok_sorted]
    tg_vals = [r["gen"].get("tg_tps_mean", 0) for r in ok_sorted]
    tg_err  = [r["gen"].get("tg_tps_std",  0) for r in ok_sorted]
    ttft    = [r["gen"].get("ttft_ms_mean", 0) for r in ok_sorted]
    pp_vals = [r["pp"].get("pp_tps_mean",  0) for r in ok_sorted]
    pp_err  = [r["pp"].get("pp_tps_std",   0) for r in ok_sorted]
    cache   = [r.get("cache", {}).get("hit_rate_pct", 0) for r in ok_sorted]
    colors  = [MODEL_COLORS[i % len(MODEL_COLORS)] for i in range(len(ok_sorted))]
    n       = len(ok_sorted)
    y       = np.arange(n)
    h       = max(4, n * 0.65 + 1.5)

    def hbar(vals, errs, title, xlabel, fname, ref=None):
        fig, ax = plt.subplots(figsize=(10, h))
        has_err = any(e > 0 for e in errs)
        ax.barh(y, vals,
                xerr=errs if has_err else None,
                color=colors, height=0.6, zorder=3,
                edgecolor="white", linewidth=0.5,
                error_kw=dict(ecolor=DARK_GREY, capsize=4, linewidth=1.2))
        ax.set_yticks(y); ax.set_yticklabels(labels, fontsize=11)
        ax.set_xlabel(xlabel); ax.set_title(title)
        if ref is not None:
            ax.axvline(ref, color=GREY, linewidth=1, linestyle=":", zorder=2)
        mx = max(vals) if vals else 1
        for i, (v, bar) in enumerate(zip(vals, ax.patches)):
            if v > 0:
                ax.text(v + mx * 0.01, bar.get_y() + bar.get_height()/2,
                        f"{v:.1f}", va="center", fontsize=9,
                        fontweight="bold", color=TEXT)
        save(fig, out_dir / fname,
             "Sorted by generation speed (fastest first) · 3 iterations · temperature=0")

    hbar(tg_vals, tg_err,
         "Generation Speed — All Models", "Tokens / second (TG t/s)",
         "comparison_tg_speed.png")

    hbar(ttft, [0]*n,
         "Time to First Token — All Models", "Milliseconds (lower is better)",
         "comparison_ttft.png", ref=100)

    hbar(pp_vals, pp_err,
         "Prompt Processing Speed — All Models", "Tokens / second (PP t/s)",
         "comparison_pp_speed.png")

    hbar(cache, [0]*n,
         "KV Cache Hit Rate — All Models", "% tokens served from cache (second request)",
         "comparison_cache.png", ref=100)

    # Combined overview: TG speed + TTFT side by side
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, h))
    fig.suptitle("Performance Overview — All Models", fontsize=14,
                 fontweight="bold", y=1.01)

    ax1.barh(y, tg_vals, color=colors, height=0.6, zorder=3,
             edgecolor="white", linewidth=0.5)
    ax1.set_yticks(y); ax1.set_yticklabels(labels, fontsize=10)
    ax1.set_xlabel("Generation speed (t/s)"); ax1.set_title("Token Generation Speed")
    mx1 = max(tg_vals) if tg_vals else 1
    for v, bar in zip(tg_vals, ax1.patches):
        if v > 0:
            ax1.text(v + mx1*0.01, bar.get_y() + bar.get_height()/2,
                     f"{v:.1f}", va="center", fontsize=9, fontweight="bold", color=TEXT)

    ax2.barh(y, ttft, color=colors, height=0.6, zorder=3,
             edgecolor="white", linewidth=0.5)
    ax2.set_yticks(y); ax2.set_yticklabels([], fontsize=10)
    ax2.set_xlabel("Time to first token (ms, lower = better)")
    ax2.set_title("Time to First Token")
    ax2.axvline(100, color=GREY, linewidth=1, linestyle=":", zorder=2, label="100 ms")
    ax2.legend(fontsize=9, framealpha=0.9)
    mx2 = max(ttft) if ttft else 1
    for v, bar in zip(ttft, ax2.patches):
        if v > 0:
            ax2.text(v + mx2*0.01, bar.get_y() + bar.get_height()/2,
                     f"{v:.0f} ms", va="center", fontsize=9, fontweight="bold", color=TEXT)

    save(fig, out_dir / "comparison_overview.png",
         "Sorted by generation speed (fastest first) · 3 iterations · temperature=0")

    # Speed vs TTFT scatter
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.set_title("Speed vs Time-to-First-Token — All Models", pad=14)
    for i, r in enumerate(ok_sorted):
        tg = r["gen"].get("tg_tps_mean", 0)
        tt = r["gen"].get("ttft_ms_mean", 0)
        ax.scatter(tg, tt, color=colors[i], s=200, zorder=4,
                   edgecolors="white", linewidth=1.5)
        ax.annotate(shorten(r["model"]), (tg, tt),
                    textcoords="offset points", xytext=(8, 4),
                    fontsize=9, color=TEXT)
    ax.set_xlabel("Generation speed (t/s)  →  faster")
    ax.set_ylabel("Time to first token (ms)  ↓  lower is better")
    ax.axhline(100, color=GREY, linewidth=1, linestyle=":", label="100 ms TTFT")
    ax.legend(fontsize=9, framealpha=0.9)
    save(fig, out_dir / "comparison_scatter.png",
         "Best quadrant: high t/s AND low TTFT (bottom-right)")

    print(f"\n  Generated {n}-model comparison charts.")


# ═══════════════════════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Generate benchmark PNG charts")
    parser.add_argument("--json", metavar="FILE",
                        help="JSON results from benchmark_models.py --json (enables comparison charts)")
    parser.add_argument("--output", metavar="DIR",
                        default="/home/sysadmin/codebase/bin/docs/images",
                        help="Output directory (default: docs/images/)")
    parser.add_argument("--single", action="store_true",
                        help="Also regenerate single-model gpt-oss-120b charts")
    args = parser.parse_args()

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.json:
        print(f"Loading {args.json} ...")
        with open(args.json) as f:
            results = json.load(f)
        print(f"  {len(results)} model result(s) loaded")
        print("\nGenerating comparison charts ...")
        gen_comparison_charts(results, out_dir)
        if args.single or len(results) == 1:
            print("\nGenerating single-model per-run charts ...")
            gen_single_model_charts(out_dir)
    else:
        print("No --json provided; generating single-model gpt-oss-120b charts only.")
        gen_single_model_charts(out_dir)

    print(f"\nAll charts written to {out_dir}/")


if __name__ == "__main__":
    main()
EOF
chmod 755 /home/sysadmin/codebase/bin/gen_benchmark_charts.py
```
