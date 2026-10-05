"""
PRC-1: merge the two probe runs and classify every configured model with the final (corrected) classifier. The first run's gpt-oss entries are superseded by the re-run that used a realistic
budget for reasoning models (the first run's 5-token step returned empty content by design). qwen and the six OpenRouter models are re-classified from the first run's recorded responses.
No network. Run from apps/backend:  PYTHONPATH=. python benchmarks/ai_search/baseline_2026_10_04/prc1_provider_audit/finalize.py
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, ".")
HERE = Path(__file__).parent
import probe as PR  # noqa: E402

first = json.loads((HERE / "probe_results.json").read_text(encoding="utf-8"))
second = json.loads((HERE / "probe_results_gptoss.json").read_text(encoding="utf-8"))
final = {}
for key, v in first["results"].items():
    if key in second["results"]:
        v = second["results"][key]
    state, ev = PR.classify(v["steps"])
    final[key] = {"state": state, "evidence": ev, "requests": len(v["steps"]), "last_step": v["steps"][-1]["step"], "last_status": v["steps"][-1]["status"],
                  "retry_after": (v["steps"][-1].get("limit_headers") or {}).get("retry-after"), "limit_headers": v["steps"][-1].get("limit_headers")}
final["gemini:gemini-3.6-flash / gemini-3.5-flash-lite"] = {"state": "NOT_TESTED", "evidence": "no Gemini key is configured in the local environment (it is configured in production); testing it needs the production key and is not part of this local diagnostic"}
final["mistral:*"] = {"state": "NOT_TESTED", "evidence": "no Mistral key is configured locally or in production"}
reset = datetime.fromtimestamp(1791158400000 / 1000, tz=timezone.utc)
(HERE / "probe_results_final.json").write_text(json.dumps({"openrouter_free_daily_reset_utc": reset.isoformat(), "classification": final}, indent=2, ensure_ascii=False), encoding="utf-8")
for k, v in final.items():
    print(f"{v['state']:20} {k:62} {v['evidence'][:150]}")
print("OpenRouter daily reset (from its X-RateLimit-Reset header):", reset.isoformat(), "=", reset.astimezone(timezone.utc).strftime("%H:%M UTC"), "= 05:30 IST")
