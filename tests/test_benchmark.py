"""Guardrails: no silent mocks, results must exist and be live-measured."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_live_results_exist_and_shape():
    p = ROOT / "data" / "live_results.json"
    assert p.exists(), "run python src/benchmark_trust.py first"
    payload = json.loads(p.read_text(encoding="utf-8"))
    assert len(payload["sites"]) == 10
    for s in payload["sites"]:
        assert "http_status" in s and "trust_100" in s
        assert 0 <= s["trust_100"] <= 100

def test_core_apis_live():
    p = ROOT / "data" / "live_results.json"
    payload = json.loads(p.read_text(encoding="utf-8"))
    ok = sum(1 for a in payload["live_apis"] if a.get("ok"))
    assert ok >= 3, f"only {ok} live APIs ok — no mock success allowed"

def test_hidden_patterns_exist():
    p = ROOT / "experiments" / "hidden_patterns.json"
    assert p.exists(), "run python src/hidden_patterns.py first"
    out = json.loads(p.read_text(encoding="utf-8"))
    assert len(out["patterns"]) >= 4
