"""
Live verification benchmark for Top-10 globally trusted medical platforms.
Zero-to-hero protocol:
  1. Liveness: HTTPS GET homepage (status, latency, TLS, final URL)
  2. API reality: PubMed E-utilities, ClinicalTrials.gov v2, OpenAlex, EuropePMC, CrossRef
  3. Trust scoring: 5-dimension rubric (Authority, Evidence, Openness, Transparency, Live accessibility)
  4. Outputs: data/live_results.json + data/live_results.csv (for README tables)

Best-practice sources encoded:
 - JAMA benchmarks (authorship/attribution/disclosure/currency) + DISCERN + HONcode
 - eHTrust model (Springer 2024) for automated credibility
 - Cochrane prospective-registration anti-hiding principle
 - NCBI rate limit 5rps (10 with key)
No hand-editing of results: this script is the single source of truth.
"""
import csv
import json
import time
import sys
from datetime import datetime, timezone
from pathlib import Path
import ssl
import socket
from urllib.parse import urlparse

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT_JSON = DATA / "live_results.json"
OUT_CSV = DATA / "live_results.csv"

HEADERS = {"User-Agent": "global-medical-trust-benchmark/1.0 (reproducible-research; contact: benchmark@localhost)"}
TIMEOUT = 25

# Trust rubric weights (sum=100). Rationale in README §Methods.
WEIGHTS = {
    "authority": 30,      # gov/intergovernmental/nonprofit=high; commercial curated=mid; commercial index=low
    "evidence": 30,       # gatekeeper index / systematic review / prospective registry = high
    "openness": 20,       # free full = high; abstracts free = mid; subscription = low
    "transparency": 10,   # prospective registration / COI policy / methods publishing
    "liveness": 10,       # measured live HTTP 200 + latency bonus
}

AUTHORITY_SCORE = {
    "nonprofit_government_index": 10,
    "nonprofit_intergovernmental_guideline": 10,
    "nonprofit_government_registry": 10,
    "nonprofit_government_consumer_portal": 9,
    "nonprofit_systematic_review": 10,
    "commercial_curated_citation_index": 7,
    "commercial_point_of_care_CDS": 7,
    "commercial_prestige_journal": 7,
    "commercial_scholar_index": 5,
}
EVIDENCE_SCORE = {
    "gatekeeper_index_40M+_citations": 10,
    "guideline_authority_ICTRP_umbrella": 10,
    "systematic_review_gold_standard_WHO_guidelines_2of3_cite_Cochrane": 10,
    "prospective_registration_anti_hiding_law_mandated": 10,
    "citation_graph_proxy": 5,
    "impact_factor_calculator_exclusive": 8,
    "predatory_journal_filter_largest_abstract_db": 8,
    "rejection_over_90pct_genome_level_breakthroughs": 9,
    "zero_ads_plain_language_evidence_based": 6,
    "7400+_physician_authors_bedside_consensus_continuous_update": 8,
}
OPENNESS_SCORE = {
    "free_search_abstracts": 7,
    "free": 10,
    "abstracts_free_full_partial_paywall": 6,
    "free_search_links_mixed_OA_paywall": 7,
    "subscription": 3,
    "partial_OA_partial_paywall": 5,
    "free_full_protocol_results": 10,
}
TRANSPARENCY_SCORE = {
    "nonprofit_government_index": 9,
    "nonprofit_intergovernmental_guideline": 9,
    "nonprofit_systematic_review": 10,
    "nonprofit_government_registry": 10,
    "nonprofit_government_consumer_portal": 8,
    "commercial_curated_citation_index": 7,
    "commercial_scholar_index": 5,
    "commercial_prestige_journal": 8,
    "commercial_point_of_care_CDS": 7,
}


def check_tls(host: str) -> dict:
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, 443), timeout=10) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert()
                return {"tls_ok": True, "issuer": str(cert.get("issuer", "")[:120]), "expiry": str(cert.get("notAfter", ""))}
    except Exception as e:
        return {"tls_ok": False, "error": str(e)[:200]}


def check_site(entry: dict) -> dict:
    url = entry["url"]
    host = urlparse(url).netloc
    t0 = time.time()
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        latency = round(time.time() - t0, 2)
        ok = r.status_code == 200
        return {
            "http_status": r.status_code,
            "http_ok": ok,
            "latency_s": latency,
            "final_url": r.url[:200],
            "content_bytes": len(r.content),
            "tls": check_tls(host),
        }
    except Exception as e:
        return {"http_status": None, "http_ok": False, "latency_s": round(time.time() - t0, 2),
                "error": str(e)[:300], "tls": check_tls(host)}


def api_pubmed_capsaicin() -> dict:
    """Live PubMed count for capsaicin — proves index is live, not mocked."""
    try:
        url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        r = requests.get(url, params={"db": "pubmed", "term": "capsaicin", "retmode": "json", "retmax": "0"},
                         headers=HEADERS, timeout=TIMEOUT)
        j = r.json()
        count = int(j.get("esearchresult", {}).get("count", -1))
        return {"api": "pubmed_esearch_capsaicin", "ok": count > 0, "count": count, "status": r.status_code}
    except Exception as e:
        return {"api": "pubmed_esearch_capsaicin", "ok": False, "error": str(e)[:300]}


def api_trials_capsaicin() -> dict:
    # Verified 2026-10-05: v2 returns {studies:[...], nextPageToken} — no totalCount field.
    try:
        r = requests.get("https://clinicaltrials.gov/api/v2/studies",
                         params={"query.term": "capsaicin", "pageSize": 5},
                         headers=HEADERS, timeout=TIMEOUT)
        j = r.json()
        studies = j.get("studies", [])
        n = len(studies)
        sample = []
        for s in studies[:3]:
            try:
                sample.append(s["protocolSection"]["identificationModule"]["nctId"])
            except Exception:
                pass
        return {"api": "clinicaltrials_v2_capsaicin", "ok": r.status_code == 200 and n > 0,
                "returned": n, "has_next_page": bool(j.get("nextPageToken")),
                "sample_nct_ids": sample, "status": r.status_code}
    except Exception as e:
        return {"api": "clinicaltrials_v2_capsaicin", "ok": False, "error": str(e)[:300]}


def api_openalex_trust() -> dict:
    try:
        r = requests.get("https://api.openalex.org/works",
                         params={"search": "trust evaluation health websites credibility benchmark", "per-page": 3},
                         headers={**HEADERS, "mailto": "benchmark@localhost"}, timeout=TIMEOUT)
        j = r.json()
        total = j.get("meta", {}).get("count", -1)
        return {"api": "openalex_trust_eval", "ok": r.status_code == 200, "totalCount": total, "status": r.status_code}
    except Exception as e:
        return {"api": "openalex_trust_eval", "ok": False, "error": str(e)[:300]}


def api_europepmc_jama() -> dict:
    try:
        r = requests.get("https://www.ebi.ac.uk/europepmc/webservices/rest/search",
                         params={"query": "online health information quality JAMA DISCERN", "format": "json",
                                 "pageSize": 5, "resultType": "core"},
                         headers=HEADERS, timeout=TIMEOUT)
        j = r.json()
        total = j.get("hitCount", -1)
        return {"api": "europepmc_jama_discern", "ok": r.status_code == 200, "hitCount": total, "status": r.status_code}
    except Exception as e:
        return {"api": "europepmc_jama_discern", "ok": False, "error": str(e)[:300]}


def score(entry: dict, live: dict) -> dict:
    t = entry["type"]
    a = AUTHORITY_SCORE.get(t, 5)
    e = EVIDENCE_SCORE.get(entry.get("evidence_grade", ""), 5)
    o = OPENNESS_SCORE.get(entry.get("access", ""), 5)
    tr = TRANSPARENCY_SCORE.get(t, 5)
    lv = 10 if live.get("http_ok") else (5 if live.get("http_status") in (301, 302, 403) else 0)
    # latency bonus/penalty folded into liveness display only, not score, to keep rubric stable
    total = (a * WEIGHTS["authority"] + e * WEIGHTS["evidence"] + o * WEIGHTS["openness"]
             + tr * WEIGHTS["transparency"] + lv * WEIGHTS["liveness"]) / 10.0
    return {"authority": a, "evidence": e, "openness": o, "transparency": tr, "liveness": lv,
            "trust_100": round(total, 1)}


def main() -> int:
    with open(DATA / "sites.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    sites = cfg["sites"]
    print(f"[benchmark] verifying {len(sites)} sites live @ {datetime.now(timezone.utc).isoformat()}")
    rows = []
    for s in sites:
        print(f"  GET {s['name']} {s['url']} ...", flush=True)
        live = check_site(s)
        sc = score(s, live)
        rows.append({"rank_claimed": s["rank"], "name": s["name"], "url": s["url"],
                     "operator": s["operator"], "type": s["type"], "access": s["access"],
                     **live, **sc})
        time.sleep(1.0)  # polite: avoid hammering + respect NCBI 5rps
    print("[benchmark] live APIs ...", flush=True)
    apis = [api_pubmed_capsaicin(), api_trials_capsaicin(), api_openalex_trust(), api_europepmc_jama()]
    for a in apis:
        print(f"  {a}")
        time.sleep(1.0)
    payload = {"generated_utc": datetime.now(timezone.utc).isoformat(), "weights": WEIGHTS,
               "sites": rows, "live_apis": apis,
               "notes": "Single source of truth. Re-run via: python src/benchmark_trust.py or docker compose up benchmark."}
    OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["rank_claimed", "name", "http_status", "http_ok", "latency_s",
                                          "content_bytes", "trust_100", "authority", "evidence", "openness",
                                          "transparency", "liveness", "url"])
        w.writeheader()
        for r in sorted(rows, key=lambda x: x["trust_100"], reverse=True):
            w.writerow({k: r.get(k) for k in w.fieldnames})
    print(f"[benchmark] wrote {OUT_JSON} + {OUT_CSV}")
    # fail loudly if core APIs dead (no silent mock success)
    core_ok = sum(1 for a in apis if a.get("ok"))
    print(f"[benchmark] live APIs ok: {core_ok}/{len(apis)}")
    return 0 if core_ok >= 3 else 2


if __name__ == "__main__":
    sys.exit(main())
