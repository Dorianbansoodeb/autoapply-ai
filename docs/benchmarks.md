# Milestone 0 model benchmarks

Machine: Apple M3, 16 GB unified memory, macOS, Ollama 0.40.15, Metal iGPU. One model loaded at a time. Weights pulled from the official Ollama registry (not redistributed). Raw numbers: [benchmarks-m0.json](benchmarks-m0.json).

| Model | License | Disk | Gen tok/s | Prompt tok/s | Ollama RSS | Wall | Schema |
|---|---|---|---|---|---|---|---|
| `phi3.5:3.8b` | MIT | 2.2 GB | 35.0 | 209.6 | 3.7 GB | 4.5 s | valid |
| `qwen2.5:7b-instruct` | Apache-2.0 | 4.7 GB | 18.3 | 110.2 | 4.8 GB | 7.1 s | valid |

Both sit in the spec’s “practical floor” band for 16 GB (7–8B plus browser). Phi-3.5 is the faster default for prep-mode drafts; Qwen 7B is slower but still interactive.

Live schema eval on Phi-3.5 (`scripts/eval_schema.py`): **50/50** JSON-valid in 476 s. That measures schema adherence, not factual support. [eval-schema-m0.json](eval-schema-m0.json).
