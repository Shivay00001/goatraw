"""
GoatRaw — Market Research Agent
Produces a structured market intelligence report:
  1. Market size & growth rate
  2. Key players + funding landscape
  3. Customer pain points
  4. Emerging trends + technologies
  5. Regulatory/compliance landscape (where relevant)
  6. Entry opportunity analysis
"""

import asyncio
import logging
from datetime import datetime

from app.services.llm_adapter import generate_json, ModelType
from app.agents.tools         import tool_search_web, tool_web_scrape, tool_extract_structured_data
from app.core.redis_client    import set_task_status, set_task_result

logger = logging.getLogger("goatraw.market_research")

MARKET_SCHEMA = {
    "market_name":       "str",
    "estimated_size":    "str",     # e.g. "$4.2B"
    "growth_rate":       "str",     # e.g. "18% CAGR"
    "key_players":       "list[str]",
    "funding_activity":  "str",
    "main_use_cases":    "list[str]",
    "customer_segments": "list[str]",
    "geography":         "str",
    "trends":            "list[str]",
}

PAIN_POINTS_SCHEMA = {
    "primary_pain_points":   "list[str]",
    "underserved_segments":  "list[str]",
    "willingness_to_pay":    "str",
    "buying_triggers":       "list[str]",
    "decision_makers":       "list[str]",  # titles of people who buy
}

SYNTHESIS_SYSTEM = """You are a senior market analyst. Produce precise, data-backed market research.
Cite specific numbers when available. Output JSON only."""


class MarketResearchAgent:
    def __init__(self, task_id: str, topic: str, focus: str = "general"):
        self.task_id = task_id
        self.topic   = topic
        self.focus   = focus   # "size" | "players" | "pains" | "trends" | "general"

    async def _search_market_overview(self) -> dict:
        queries = [
            f"{self.topic} market size 2025 growth rate billion",
            f"{self.topic} industry report funding landscape",
            f"top companies {self.topic} market share 2025",
        ]
        all_snippets = []
        for q in queries:
            r = await tool_search_web(q, num_results=6)
            for res in r.get("results", [])[:4]:
                all_snippets.append(res.get("snippet", ""))

        combined = " ".join(all_snippets)[:6000]
        extracted = await tool_extract_structured_data(text=combined, schema=MARKET_SCHEMA)
        return extracted.get("data", {})

    async def _search_pain_points(self) -> dict:
        queries = [
            f"{self.topic} problems challenges pain points reddit",
            f"why businesses struggle with {self.topic}",
            f"{self.topic} customer complaints missing features",
        ]
        snippets = []
        for q in queries:
            r = await tool_search_web(q, num_results=5)
            for res in r.get("results", [])[:3]:
                snippets.append(res.get("snippet", ""))

        combined = " ".join(snippets)[:5000]
        extracted = await tool_extract_structured_data(text=combined, schema=PAIN_POINTS_SCHEMA)
        return extracted.get("data", {})

    async def _search_recent_funding(self) -> list:
        r = await tool_search_web(
            f"{self.topic} startup funding raised Series A B 2024 2025",
            num_results=8,
        )
        funding_news = []
        for res in r.get("results", [])[:6]:
            title   = res.get("title", "")
            snippet = res.get("snippet", "")
            if any(kw in title.lower() + snippet.lower() for kw in ["raised", "funding", "series", "million", "billion"]):
                funding_news.append({
                    "headline": title,
                    "detail":   snippet[:200],
                    "url":      res.get("url", ""),
                })
        return funding_news

    async def _search_trends(self) -> list:
        r = await tool_search_web(
            f"{self.topic} emerging trends technology 2025 future",
            num_results=8,
        )
        trends = []
        for res in r.get("results", [])[:5]:
            trends.append({
                "title":   res.get("title", ""),
                "snippet": res.get("snippet", "")[:200],
            })
        return trends

    async def _synthesise_report(
        self,
        overview:      dict,
        pain_points:   dict,
        funding_news:  list,
        trends:        list,
    ) -> dict:
        prompt = f"""Synthesise this market research data into an actionable report.

Topic: {self.topic}
Focus: {self.focus}

Overview Data:  {overview}
Pain Points:    {pain_points}
Funding News:   {funding_news[:5]}
Trends:         {trends[:5]}

Return JSON:
{{
  "executive_summary": "3-4 sentence market snapshot with numbers",
  "market_size":       "specific figure + growth rate",
  "top_players":       ["Company A (funding)", "Company B"],
  "key_pain_points":   ["Pain 1", "Pain 2", "Pain 3"],
  "biggest_trends":    ["Trend 1", "Trend 2"],
  "entry_opportunities": ["specific opportunity 1", "opportunity 2"],
  "recommended_positioning": "how a new entrant should position",
  "icp": {{
    "company_type":    "e.g. B2B SaaS 10-200 employees",
    "job_titles":      ["CTO", "VP Engineering"],
    "trigger_events":  ["hiring surge", "funding round"],
    "budget_range":    "e.g. $500-$5000/month"
  }},
  "market_maturity": "emerging|growing|mature|declining"
}}"""

        return await generate_json(prompt, model_type=ModelType.SMART, system_prompt=SYNTHESIS_SYSTEM)

    async def run(self) -> dict:
        logger.info(f"[{self.task_id}] Market research: '{self.topic}'")
        await set_task_status(self.task_id, "executing")

        overview_task  = asyncio.create_task(self._search_market_overview())
        pains_task     = asyncio.create_task(self._search_pain_points())
        funding_task   = asyncio.create_task(self._search_recent_funding())
        trends_task    = asyncio.create_task(self._search_trends())

        overview, pain_points, funding_news, trends = await asyncio.gather(
            overview_task, pains_task, funding_task, trends_task
        )

        report = await self._synthesise_report(overview, pain_points, funding_news, trends)

        result = {
            "task_id":    self.task_id,
            "goal":       f"Market research: {self.topic}",
            "agent_type": "market_research",
            "status":     "completed",
            "output": {
                "summary": report.get("executive_summary", f"Market research on {self.topic} complete."),
                "status":  "success",
                "data": {
                    "topic":          self.topic,
                    "market_size":    report.get("market_size"),
                    "top_players":    report.get("top_players", []),
                    "pain_points":    report.get("key_pain_points", []),
                    "trends":         report.get("biggest_trends", []),
                    "opportunities":  report.get("entry_opportunities", []),
                    "positioning":    report.get("recommended_positioning"),
                    "icp":            report.get("icp", {}),
                    "maturity":       report.get("market_maturity"),
                    "raw": {
                        "overview":      overview,
                        "pain_points":   pain_points,
                        "funding_news":  funding_news,
                        "trend_sources": trends,
                    },
                },
                "stats": {
                    "funding_news_found": len(funding_news),
                    "trends_found":       len(trends),
                },
                "next_steps": [
                    "Schedule weekly market pulse monitoring",
                    "Run competitor analysis on top_players",
                    "Build ICP-targeted lead list",
                ],
            },
            "completed_at": datetime.utcnow().isoformat(),
            "steps_taken":  5,
        }

        await set_task_status(self.task_id, "completed")
        await set_task_result(self.task_id, result)
        return result
