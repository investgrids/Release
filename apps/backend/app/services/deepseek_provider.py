"""
DeepSeekProvider — production implementation using DeepSeek's OpenAI-compatible API.
All calls are async (httpx). JSON is extracted from responses with a markdown-strip helper.
"""
from __future__ import annotations

import json
import structlog
from typing import Any, Dict, List

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.services.ai_provider import AIProvider

logger = structlog.get_logger(__name__)

_TIMEOUT = 45.0


class DeepSeekProvider(AIProvider):
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deepseek.com/v1",
        model: str = "deepseek-chat",
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    # ── Internal helpers ──────────────────────────────────────────────────────

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(httpx.HTTPStatusError),
        reraise=True,
    )
    async def _chat(self, system: str, user: str, max_tokens: int = 2048) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.1,
            "max_tokens": max_tokens,
        }
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers=self._headers,
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]

    @staticmethod
    def _parse_json(text: str) -> Any:
        """Extract JSON from response, stripping markdown code fences if present."""
        text = text.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            # drop first line (```json) and last (```)
            inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
            text = "\n".join(inner)
        return json.loads(text)

    async def _safe_json_call(
        self, system: str, user: str, fallback: Any, max_tokens: int = 2048
    ) -> Any:
        try:
            raw = await self._chat(system, user, max_tokens=max_tokens)
            return self._parse_json(raw)
        except Exception as exc:
            logger.warning("AI call failed (%s): %s", type(exc).__name__, exc)
            return fallback

    # ── Legacy pipeline methods ───────────────────────────────────────────────

    async def classify_event(self, text: str) -> Dict[str, Any]:
        return await self._safe_json_call(
            system=(
                'You are a financial event classifier for Indian capital markets. '
                'Return JSON only: '
                '{"category": "policy|corporate|macro|earnings|regulatory|market", '
                '"confidence": 0.0-1.0, "subcategory": "string"}'
            ),
            user=f"Classify this event:\n{text[:1200]}",
            fallback={"category": "macro", "confidence": 0.7, "subcategory": "general"},
        )

    async def summarize_news(self, text: str) -> str:
        try:
            return await self._chat(
                system=(
                    "You are a financial analyst covering Indian markets. "
                    "Summarize the following in 2-3 concise sentences focused on market impact."
                ),
                user=text[:2000],
            )
        except Exception as exc:
            logger.warning("summarize_news failed: %s", exc)
            return text[:300]

    async def generate_story(self, context: Dict[str, Any]) -> str:
        try:
            return await self._chat(
                system=(
                    "You are a market storyteller for Indian capital markets. "
                    "Write an engaging 150-word story about the given market theme."
                ),
                user=json.dumps(context),
            )
        except Exception as exc:
            logger.warning("generate_story failed: %s", exc)
            return "Market story generation unavailable."

    async def generate_radar(self, context: Dict[str, Any]) -> Dict[str, Any]:
        return await self._safe_json_call(
            system=(
                'You are an investment opportunity analyst for Indian equities. '
                'Return JSON only: {"theme": "string", "score": 0-100, '
                '"reason": "string", "time_horizon": "short|medium|long"}'
            ),
            user=json.dumps(context),
            fallback={"theme": "Market Opportunity", "score": 70, "reason": "Analysis unavailable", "time_horizon": "medium"},
        )

    # ── Event detail pipeline methods ─────────────────────────────────────────

    async def summarize_event(
        self, title: str, text: str, source: str
    ) -> Dict[str, Any]:
        fallback = {
            "summary": title,
            "why_it_matters": "This event may have market implications.",
            "key_bullets": [title],
            "immediate_impact": "neutral",
            "long_term_impact": "neutral",
            "risk_factors": [],
            "opportunities": [],
        }
        return await self._safe_json_call(
            system="""You are a senior Indian capital markets analyst.
Return JSON only (no extra text):
{
  "summary": "2-sentence plain-English event summary",
  "why_it_matters": "1 sentence on market significance",
  "key_bullets": ["bullet 1", "bullet 2", "bullet 3"],
  "immediate_impact": "positive|negative|neutral",
  "long_term_impact": "positive|negative|neutral",
  "risk_factors": ["risk 1", "risk 2"],
  "opportunities": ["opportunity 1", "opportunity 2"]
}""",
            user=f"Source: {source}\nTitle: {title}\n\nDetails: {text[:2500]}",
            fallback=fallback,
            max_tokens=1024,
        )

    async def extract_companies(
        self, title: str, text: str
    ) -> List[Dict[str, Any]]:
        result = await self._safe_json_call(
            system="""You are an Indian equity markets analyst.
Extract all NSE-listed companies directly affected by this event.
Return a JSON array only (empty array if none apply):
[{"symbol": "NSE_TICKER", "name": "Full Company Name", "impact_type": "beneficiary|loser|neutral", "reason": "1-sentence reason", "impact_score": 0.0-10.0}]
Use correct NSE ticker symbols (RELIANCE, TCS, HDFCBANK, INFY, etc.).
Limit to 10 companies maximum.""",
            user=f"Title: {title}\n\nDetails: {text[:2500]}",
            fallback=[],
            max_tokens=1024,
        )
        return result if isinstance(result, list) else []

    async def extract_sectors(
        self, title: str, text: str
    ) -> List[Dict[str, Any]]:
        result = await self._safe_json_call(
            system="""You are an Indian equity sector analyst.
Identify sectors most affected by this event.
Return a JSON array only:
[{"sector": "sector name", "impact": "positive|negative|neutral", "impact_score": 0.0-10.0, "reason": "1-sentence reason"}]
Use standard NSE sector names: Banking, IT, Pharma, Auto, FMCG, Energy, Infrastructure,
Metals, Telecom, Realty, Defence, Chemicals, Agriculture, Financial Services.
Return 1-5 most relevant sectors only.""",
            user=f"Title: {title}\n\nDetails: {text[:2500]}",
            fallback=[],
            max_tokens=512,
        )
        return result if isinstance(result, list) else []

    async def generate_timeline(
        self, title: str, text: str, event_type: str
    ) -> List[Dict[str, Any]]:
        result = await self._safe_json_call(
            system="""You are a market event analyst.
Generate a 4-5 phase chronological timeline for this event.
Return a JSON array only:
[{"date": "YYYY-MM-DD or descriptive label", "title": "Phase title", "description": "1-2 sentences", "order": 1}]
Phases should cover: background context, triggering event, immediate market reaction, near-term outlook, long-term implication.""",
            user=f"Event type: {event_type}\nTitle: {title}\n\nDetails: {text[:1800]}",
            fallback=[],
            max_tokens=1024,
        )
        return result if isinstance(result, list) else []

    async def generate_impact_analysis(
        self,
        title: str,
        text: str,
        companies: List[Dict],
        sectors: List[Dict],
    ) -> Dict[str, Any]:
        context = {
            "title": title,
            "excerpt": text[:800],
            "beneficiary_count": sum(1 for c in companies if c.get("impact_type") == "beneficiary"),
            "loser_count": sum(1 for c in companies if c.get("impact_type") == "loser"),
            "sectors": [s.get("sector") for s in sectors],
        }
        fallback = {
            "impact_score": 60,
            "confidence": 65,
            "market_reaction": {
                "short_term": "neutral", "medium_term": "neutral",
                "volatility": "medium", "sentiment": "neutral",
            },
            "analysis": {
                "bull_case": "Positive fundamentals could drive upside.",
                "bear_case": "Macro headwinds may cap gains.",
                "base_case": "Neutral near-term outlook.",
                "key_risks": [], "catalysts": [],
            },
        }
        return await self._safe_json_call(
            system="""You are a risk analyst specialising in Indian capital markets.
Return JSON only:
{
  "impact_score": 0-100,
  "confidence": 0-100,
  "market_reaction": {
    "short_term": "bullish|bearish|neutral",
    "medium_term": "bullish|bearish|neutral",
    "volatility": "low|medium|high",
    "sentiment": "positive|negative|neutral"
  },
  "analysis": {
    "bull_case": "1-sentence bull scenario",
    "bear_case": "1-sentence bear scenario",
    "base_case": "1-sentence base scenario",
    "key_risks": ["risk 1", "risk 2"],
    "catalysts": ["catalyst 1", "catalyst 2"]
  }
}""",
            user=json.dumps(context),
            fallback=fallback,
            max_tokens=1024,
        )

    async def find_similar_events(
        self,
        title: str,
        sectors: List[str],
        candidate_events: List[Dict],
    ) -> List[Dict[str, Any]]:
        if not candidate_events:
            return []
        context = {
            "current_event": title,
            "current_sectors": sectors,
            "candidates": [
                {"id": e["id"], "title": e["title"], "sectors": e.get("sectors", [])}
                for e in candidate_events[:20]
            ],
        }
        result = await self._safe_json_call(
            system="""You are an event similarity analyst.
From the candidate events, identify those most similar to the current event.
Return a JSON array only (empty if none are genuinely similar):
[{"event_id": "id", "similarity_score": 0.0-1.0, "reason": "1-sentence reason"}]
Return top 3 most similar events.""",
            user=json.dumps(context),
            fallback=[],
            max_tokens=512,
        )
        return result if isinstance(result, list) else []

    async def generate_graph(
        self,
        title: str,
        companies: List[Dict],
        sectors: List[Dict],
    ) -> Dict[str, Any]:
        context = {
            "event": title,
            "companies": [
                {"symbol": c.get("symbol"), "impact": c.get("impact_type")}
                for c in companies[:8]
            ],
            "sectors": [s.get("sector") for s in sectors[:5]],
        }
        fallback = {"nodes": [], "edges": []}
        result = await self._safe_json_call(
            system="""You are a financial network graph designer.
Return JSON only:
{
  "nodes": [
    {"node_id": "unique_id", "label": "display name", "node_type": "event|company|sector|policy|index", "node_metadata": {}}
  ],
  "edges": [
    {"source": "node_id", "target": "node_id", "edge_relationship": "impacts|benefits|harms|drives|correlates"}
  ]
}
Include the event as a central node. Connect it to companies and sectors. Max 15 nodes.""",
            user=json.dumps(context),
            fallback=fallback,
            max_tokens=1536,
        )
        if not isinstance(result, dict):
            return fallback
        return result

