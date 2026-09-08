"""
AIProvider — abstract interface for all AI operations.
Implement a concrete provider and register it in provider_factory.py.
The AI provider name is controlled by the AI_PROVIDER env variable.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List


class AIProvider(ABC):

    # ── Legacy pipeline methods ───────────────────────────────────────────────

    @abstractmethod
    async def classify_event(self, text: str) -> Dict[str, Any]:
        """Classify text into event category. Returns {category, confidence, subcategory}."""
        raise NotImplementedError

    @abstractmethod
    async def summarize_news(self, text: str) -> str:
        """Summarize a news article into 2-3 sentences."""
        raise NotImplementedError

    @abstractmethod
    async def generate_story(self, context: Dict[str, Any]) -> str:
        """Generate a market narrative story from context dict."""
        raise NotImplementedError

    @abstractmethod
    async def generate_radar(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate an opportunity radar entry from context dict."""
        raise NotImplementedError

    # ── Event detail pipeline methods ─────────────────────────────────────────

    @abstractmethod
    async def summarize_event(
        self, title: str, text: str, source: str
    ) -> Dict[str, Any]:
        """
        Return structured event summary:
        {summary, why_it_matters, key_bullets, immediate_impact,
         long_term_impact, risk_factors, opportunities}
        """
        raise NotImplementedError

    @abstractmethod
    async def extract_companies(
        self, title: str, text: str
    ) -> tuple[List[Dict[str, Any]], str]:
        """
        Return (list of affected companies, integrity_status):
        [{symbol, name, impact_type (beneficiary|loser|neutral), reason, impact_score}]
        integrity_status is measurement_semantics.IntegrityStatus.VALID/FALLBACK.value
        (Event Enrichment R1, 2026-09-08) -- an empty list alone cannot tell a caller
        whether the AI genuinely found zero companies or this call itself failed.
        """
        raise NotImplementedError

    @abstractmethod
    async def extract_sectors(
        self, title: str, text: str
    ) -> tuple[List[Dict[str, Any]], str]:
        """
        Return (list of affected sectors, integrity_status) -- see extract_companies.
        [{sector, impact (positive|negative|neutral), impact_score, reason}]
        """
        raise NotImplementedError

    @abstractmethod
    async def generate_timeline(
        self, title: str, text: str, event_type: str
    ) -> List[Dict[str, Any]]:
        """
        Return chronological timeline:
        [{date, title, description, order}]
        """
        raise NotImplementedError

    @abstractmethod
    async def generate_impact_analysis(
        self,
        title: str,
        text: str,
        companies: List[Dict],
        sectors: List[Dict],
    ) -> Dict[str, Any]:
        """
        Return impact scoring and market reaction:
        {impact_score, confidence, market_reaction: {short_term, medium_term, volatility, sentiment},
         analysis: {bull_case, bear_case, base_case, key_risks, catalysts}}
        """
        raise NotImplementedError

    @abstractmethod
    async def find_similar_events(
        self,
        title: str,
        sectors: List[str],
        candidate_events: List[Dict],
    ) -> List[Dict[str, Any]]:
        """
        From a list of DB-candidate events, rank by similarity:
        [{event_id, similarity_score, reason}]
        """
        raise NotImplementedError

    @abstractmethod
    async def generate_graph(
        self,
        title: str,
        companies: List[Dict],
        sectors: List[Dict],
    ) -> Dict[str, Any]:
        """
        Return network graph:
        {nodes: [{node_id, label, node_type, node_metadata}],
         edges: [{source, target, edge_relationship}]}
        """
        raise NotImplementedError
