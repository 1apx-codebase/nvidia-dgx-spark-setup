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
