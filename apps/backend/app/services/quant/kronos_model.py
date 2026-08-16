"""
Kronos pretrained-model wrapper — Phase 2C.

Vendored model code: app/services/quant/kronos_vendor/model/ (see that
folder's README.md for provenance/license). Pretrained weights are
downloaded from Hugging Face Hub on first use and cached by
huggingface_hub's own mechanism — nothing is bundled in this repo.

Owner instruction, followed literally: run the RELEASED PRETRAINED
model first, no fine-tuning. This module never touches
kronos_vendor/model's training code path — only KronosTokenizer.
from_pretrained() / Kronos.from_pretrained() / KronosPredictor.predict()
are called, the same three calls the upstream README's own inference
example uses.

Model choice: Kronos-small (24.7M params, max_context=512) — the
smaller of the two fully open-source checkpoints (Kronos-base,
102.3M params, is the other; Kronos-large is closed-source). Small is
the right first choice for "does pretrained Kronos work on Indian
equities at all" (owner's own framing) — base is a straightforward
swap (one constant) once/if that question is answered.

Output shape matches baselines.BaselineResult exactly (same field
names) so Kronos and the five baselines can be evaluated through
identical downstream code — Phase 2C's own requirement that Kronos
receive the same information boundary and be scored the same way as
the baselines it has to beat.
"""
from __future__ import annotations

import sys
import os
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import pandas as pd
import structlog

log = structlog.get_logger(__name__)

_VENDOR_DIR = os.path.join(os.path.dirname(__file__), "kronos_vendor")
if _VENDOR_DIR not in sys.path:
    sys.path.insert(0, _VENDOR_DIR)

TOKENIZER_REPO = "NeoQuasar/Kronos-Tokenizer-base"
MODEL_REPO = "NeoQuasar/Kronos-small"
MODEL_VERSION = "kronos-small-pretrained-v1"   # Phase 2B §27 — distinct from baseline-* model_versions

# Phase 2C verdict (owner decision, recorded here as the single source of
# truth for this model's status — not a comment that will drift from
# reality). 49 symbols x 6 walk-forward dates x 3 horizons (1/7/30
# sessions), same information boundary as the five baselines, zero
# leakage: Kronos-small-pretrained did not beat the strongest baseline
# (ma_momentum) on direction accuracy, balanced accuracy, or rank IC at
# any horizon. Not broken — the inference pipeline, shadow isolation, and
# evaluation wiring all work correctly — just not evidence of an edge.
# Left installed and frozen: not promoted, not deleted, not fine-tuned,
# not upgraded to Kronos-base/large until Phase 2D establishes whether
# ANY of the cheap baselines carry a signal that survives a much larger
# walk-forward study. Do not change this status without a new validation
# run backing it.
STATUS = "EXPERIMENTAL_NOT_PROMOTED"
STATUS_REASON = "Did not outperform simple baselines (ma_momentum, previous_return) in Phase 2C validation (49 symbols x 6 dates x 3 horizons)."

_SIDEWAYS_BAND_PCT = 0.15   # same threshold baselines.py uses — apples-to-apples direction bucketing

_predictor = None   # lazy singleton — loading the model is real I/O + memory, do it once per process


@dataclass
class KronosResult:
    model_name: str
    direction: str
    expected_return: float | None
    expected_volatility: float | None
    ok: bool               # False if inference failed / was skipped — caller must not fabricate a prediction
    reason: str | None = None


def _direction_from_return(pct: float) -> str:
    if pct >= _SIDEWAYS_BAND_PCT:
        return "up"
    if pct <= -_SIDEWAYS_BAND_PCT:
        return "down"
    return "sideways"


def is_available() -> bool:
    """Cheap check: can we even try to load Kronos (torch importable)?
    Does NOT download weights — that only happens on first real predict
    call, inside get_predictor()."""
    try:
        import torch  # noqa: F401
        return True
    except ImportError:
        return False


def get_predictor():
    """Loads (once) and returns the KronosPredictor. Raises on failure —
    callers must catch and degrade to data_quality="model_unavailable"
    (Phase 2A §29: Kronos is optional, the rest of the app must be
    unaffected by it failing to load)."""
    global _predictor
    if _predictor is not None:
        return _predictor

    from model import Kronos, KronosTokenizer, KronosPredictor  # vendored package

    log.info("kronos.loading_model", tokenizer=TOKENIZER_REPO, model=MODEL_REPO)
    tokenizer = KronosTokenizer.from_pretrained(TOKENIZER_REPO)
    model = Kronos.from_pretrained(MODEL_REPO)
    _predictor = KronosPredictor(model, tokenizer, device="cpu", max_context=512)
    log.info("kronos.model_loaded", device="cpu")
    return _predictor


def _business_dates_from(start: date, n: int) -> list[date]:
    """n consecutive real calendar dates starting the day after `start`,
    weekends skipped — used ONLY to label prediction output rows when
    real future trading dates aren't already known to the caller (see
    module docstring: the backtest path passes REAL historical trading
    dates instead, since it already has them)."""
    out = []
    d = start
    while len(out) < n:
        d = d + timedelta(days=1)
        if d.weekday() < 5:
            out.append(d)
    return out


def predict(
    bar_dates: list[date],
    closes: list[float],
    opens: list[float] | None = None,
    highs: list[float] | None = None,
    lows: list[float] | None = None,
    volumes: list[float | None] | None = None,
    future_dates: list[date] | None = None,
) -> KronosResult:
    """Run pretrained Kronos over a strictly-historical OHLC(V) window
    (no lookahead — caller truncates, same discipline as baselines.py)
    and predict `len(future_dates)` bars ahead (default: 1, next
    session). `future_dates` should be the REAL known future trading
    dates when backtesting (Phase 2A §12's trading-day-precise horizon
    definitions) — using real calendar business-day filler only when
    the true dates aren't known (e.g. a genuine forward/live call).

    Returns KronosResult(ok=False) on any failure — model unavailable,
    insufficient context, bad input — never raises, matching every
    other optional-signal convention in this app (Phase 2A §29).
    """
    if len(closes) < 30:
        return KronosResult(MODEL_VERSION, "sideways", None, None, ok=False, reason="insufficient_history")

    try:
        predictor = get_predictor()
    except Exception as exc:
        log.warning("kronos.model_load_failed", error=str(exc)[:200])
        return KronosResult(MODEL_VERSION, "sideways", None, None, ok=False, reason="model_unavailable")

    context = min(len(closes), 512)   # Kronos-small's own max_context
    o = (opens or closes)[-context:]
    h = (highs or closes)[-context:]
    l = (lows or closes)[-context:]
    c = closes[-context:]
    v = [(x if x is not None else 0.0) for x in (volumes or [0.0] * len(closes))][-context:]
    x_dates = bar_dates[-context:]

    pred_len = len(future_dates) if future_dates else 1
    y_dates = future_dates or _business_dates_from(x_dates[-1], pred_len)

    df = pd.DataFrame({"open": o, "high": h, "low": l, "close": c, "volume": v})
    x_timestamp = pd.Series(pd.to_datetime(x_dates))
    y_timestamp = pd.Series(pd.to_datetime(y_dates))

    try:
        pred_df = predictor.predict(
            df=df, x_timestamp=x_timestamp, y_timestamp=y_timestamp,
            pred_len=pred_len, T=1.0, top_p=0.9, sample_count=1, verbose=False,
        )
    except Exception as exc:
        log.warning("kronos.inference_failed", error=str(exc)[:200])
        return KronosResult(MODEL_VERSION, "sideways", None, None, ok=False, reason="inference_error")

    predicted_close = float(pred_df["close"].iloc[-1])
    last_actual_close = c[-1]
    if last_actual_close <= 0 or np.isnan(predicted_close):
        return KronosResult(MODEL_VERSION, "sideways", None, None, ok=False, reason="invalid_output")

    pct = round((predicted_close / last_actual_close - 1) * 100, 4)

    # Volatility: same rolling-stdev-of-real-returns measurement
    # baselines.py uses, NOT derived from Kronos's own output — keeps
    # this dimension directly comparable across all six models rather
    # than mixing "real historical vol" and "model-implied vol".
    rets = [round((c[i] / c[i - 1] - 1) * 100, 4) for i in range(1, len(c)) if c[i - 1] > 0]
    vol = round(float(np.std(rets[-20:])), 3) if len(rets) >= 5 else None

    return KronosResult(MODEL_VERSION, _direction_from_return(pct), pct, vol, ok=True)
