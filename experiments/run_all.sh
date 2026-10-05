#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -d .venv ]; then python3 -m venv .venv; fi
.venv/bin/pip install -q -r requirements.txt
.venv/bin/python src/benchmark_trust.py
.venv/bin/python src/hidden_patterns.py
.venv/bin/python -m pytest -q tests/
echo "DONE: see data/live_results.json data/live_results.csv experiments/hidden_patterns.json"
