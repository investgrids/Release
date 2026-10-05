"""
Request-scoped latency budget (Step 3.4H.2b).

One ABSOLUTE deadline per interactive AI Search request, carried in a ContextVar so every stage (classifier, retrieval, provider fallback chain, finalization) shares the same clock:
no stage can start with a fresh budget of its own. It is set only by the HTTP routes (`scope()`); background callers of the same functions never set it, so with no deadline active every
helper here returns None and the callers behave exactly as they did before.

The numbers are provisional (settings.ai_search_*), to be tuned from production-chain measurements (3.4H.4), not validated thresholds. A total budget of 0 disables the whole mechanism.

  remaining()  seconds to the absolute deadline
  usable()     remaining() minus the finalization reserve: what a provider attempt may spend, so Gate B and assembly can still run
  sub_budget() a nested, earlier deadline for a cheap step (the market-pulse classifier); it can never extend the parent and never touches the reserve
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field


@dataclass
class _State:
    deadline: float                      # absolute time.monotonic() value
    reserve: float                       # seconds kept back for authorization/assembly
    min_attempt: float                   # smallest usable budget worth starting a provider attempt with
    attempt_cap: float                   # longest a single provider attempt may run under the budget
    flags: dict = field(default_factory=lambda: {"expired": False})


_var: ContextVar[_State | None] = ContextVar("request_deadline", default=None)


def _settings():
    from app.core.config import settings
    return settings


@contextmanager
def scope(total: float | None = None, reserve: float | None = None, min_attempt: float | None = None, attempt_cap: float | None = None):
    """Establish the request deadline. Restores the previous value on exit (no token: safe when an async generator is resumed from a different context)."""
    s = _settings()
    total = s.ai_search_total_budget_seconds if total is None else total
    previous = _var.get()
    if total and total > 0:
        _var.set(_State(
            deadline=time.monotonic() + total,
            reserve=s.ai_search_finalization_reserve_seconds if reserve is None else reserve,
            min_attempt=s.ai_search_min_provider_attempt_seconds if min_attempt is None else min_attempt,
            attempt_cap=s.ai_search_provider_attempt_cap_seconds if attempt_cap is None else attempt_cap,
        ))
    try:
        yield
    finally:
        _var.set(previous)


@contextmanager
def sub_budget(seconds: float, min_attempt: float = 1.0):
    """A nested, earlier deadline. No-op when no request deadline is active. The parent's reserve is already excluded from the sub deadline, so the sub-budget carries none of its own."""
    parent = _var.get()
    if parent is None or not seconds or seconds <= 0:
        yield
        return
    now = time.monotonic()
    sub = _State(deadline=min(parent.deadline - parent.reserve, now + seconds), reserve=0.0, min_attempt=min(parent.min_attempt, min_attempt), attempt_cap=parent.attempt_cap)
    _var.set(sub)
    try:
        yield
    finally:
        _var.set(parent)


def active() -> bool:
    return _var.get() is not None


def remaining() -> float | None:
    st = _var.get()
    return None if st is None else st.deadline - time.monotonic()


def usable() -> float | None:
    st = _var.get()
    return None if st is None else st.deadline - st.reserve - time.monotonic()


def min_attempt() -> float | None:
    st = _var.get()
    return None if st is None else st.min_attempt


def attempt_cap() -> float | None:
    st = _var.get()
    return None if st is None else st.attempt_cap


def mark_expired() -> None:
    st = _var.get()
    if st is not None:
        st.flags["expired"] = True


def expired() -> bool:
    st = _var.get()
    return bool(st is not None and st.flags["expired"])
