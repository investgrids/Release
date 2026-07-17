"""Intent specification — declares what an intent needs, nothing else."""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class IntentSpec:
    """
    Every intent module registers exactly one of these. The orchestrator
    reads `retrievers` to decide what to fetch and `template` to decide how
    to render the answer — it never branches on the intent name itself.

    Classification patterns live here (not in a separate lookup table) so
    that adding a new intent in a future phase is a single new module: the
    fast classifier automatically considers it without any other file
    needing an edit. `priority` breaks ties when multiple intents' patterns
    match the same query — lower runs first, so more specific intents (e.g.
    event_impact's named-policy patterns) can be checked before broad
    catch-alls (e.g. news_intelligence).
    """
    key: str
    label: str                  # human-readable, e.g. "Investment Decision"
    retrievers: list[str]       # RETRIEVER_REGISTRY keys to invoke for this intent
    template: str                # TEMPLATE_REGISTRY key to render the answer with
    decision_profile: str        # hint for decision engine: "verdict" | "informational"
    patterns: tuple[str, ...] = field(default_factory=tuple)   # regex patterns, case-insensitive
    priority: int = 50
    is_default: bool = False     # exactly one registered intent should set this True

    def compiled_patterns(self) -> list[re.Pattern]:
        return [re.compile(p, re.IGNORECASE) for p in self.patterns]
