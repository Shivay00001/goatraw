"""
GoatRaw — Competitor Analysis Agent
Fully wired competitor intelligence agent:
  1. Find competitor's main website + pricing page
  2. Scrape features, pricing tiers, positioning
  3. Search for reviews and complaints
  4. Extract G2/Capterra/Trustpilot sentiment
  5. LinkedIn: find their team size + recent hires
  6. Synthesise: SWOT-style competitive brief
"""

import asyncio
import logging
from datetime import datetime

from app.services.llm_adapter  import generate_json, generate, ModelType
from app.agents.tools          import tool_search_web, tool_web_scrape, tool_extract_structured_data
from app.core.redis_client     import set_task_status, set_task_result

logger = logging.getLogger("goatraw.competitor_agent")

COMPETITOR_SCHEMA = {
    "company_name":    "str",
    "tagline":         "str",
    "pricing_model":   "str",          # free / freemium / paid / usage-based
    "pricing_tiers":   "list[str]",    # ['Starter $29/mo', 'Pro $99/mo']
    "key_features":    "list[str]",
    "target_customer": "str",
    "founded":         "str",
    "team_size":       "str",
    "funding":         "str",
    "tech_stack":      "list[str]",
}

REVIEW_SCHEMA = {
    "overall_rating":   "float",
    "positive_themes":  "list[str]",
    "negative_themes":  "list[str]",
    "common_complaints":"list[str]",
    "compared_to":      "list[str]",   # products users compare it to
}

SWOT_SYSTEM_PROMPT = """You are a strategic business analyst producing a competitor SWOT brief.
Be precise, evidence-based, and actionable. Format as JSON only."""


class CompetitorAnalysisAgent:
    def __init__(self, task_id: str, competitor_name: str, your_product: str, industry: str = ""):
        self.task_id         = task_id
        self.competitor_name = competitor_name
        self.your_product    = your_product
        self.industry        = industry

    # ── Step 1: Find & scrape main site ──────────────────────

    async def _get_website_data(self) -> dict:
        search = await tool_search_web(
            f"{self.competitor_name} official website pricing features",
            num_results=5,
        )
        results = search.get("results", [])
        # Find the official site (usually first result)
        website_url = next(
            (r["url"] for r in results if self.competitor_name.lower().split()[0] in r["url"].lower()),
            results[0]["url"] if results else "",
        )
        if not website_url:
            return {}

        page = await tool_web_scrape(website_url)
        data = await tool_extract_structured_data(
            text=page.get("content", "")[:6000],
            schema=COMPETITOR_SCHEMA,
        )
        return {"website": website_url, "data": data.get("data", {}), "page_title": page.get("title", "")}

    # ── Step 2: Scrape pricing page ───────────────────────────

    async def _get_pricing(self, base_url: str) -> dict:
        pricing_url = base_url.rstrip("/") + "/pricing"
        page = await tool_web_scrape(pricing_url)
        if page.get("status") != "success" or len(page.get("content", "")) < 100:
            search = await tool_search_web(f"{self.competitor_name} pricing plans 2025")
            results = search.get("results", [])
            text = " ".join(r.get("snippet", "") for r in results[:3])
        else:
            text = page.get("content", "")

        extracted = await tool_extract_structured_data(
            text=text[:4000],
            schema={
                "has_free_tier":  "bool",
                "pricing_tiers":  "list[{name: str, price: str, features: list[str]}]",
                "pricing_model":  "str",  # per-seat / usage / flat / freemium
                "free_trial":     "str",
            },
        )
        return extracted.get("data", {})

    # ── Step 3: Reviews & sentiment ───────────────────────────

    async def _get_review_sentiment(self) -> dict:
        queries = [
            f"{self.competitor_name} reviews G2 complaints problems",
            f"{self.competitor_name} vs alternatives reddit",
            f"site:capterra.com {self.competitor_name} review",
        ]
        texts = []
        for q in queries:
            r = await tool_search_web(q, num_results=5)
            for result in r.get("results", [])[:3]:
                texts.append(result.get("snippet", ""))

        combined = " ".join(texts)[:5000]
        extracted = await tool_extract_structured_data(text=combined, schema=REVIEW_SCHEMA)
        return extracted.get("data", {})

    # ── Step 4: News & recent activity ───────────────────────

    async def _get_recent_news(self) -> list:
        search = await tool_search_web(
            f"{self.competitor_name} news funding product launch 2025",
            num_results=8,
        )
        news = []
        for r in search.get("results", [])[:5]:
            news.append({
                "title":   r.get("title", ""),
                "snippet": r.get("snippet", "")[:200],
                "url":     r.get("url", ""),
            })
        return news

    # ── Step 5: SWOT synthesis ────────────────────────────────

    async def _synthesise_swot(
        self,
        website_data: dict,
        pricing_data: dict,
        review_data:  dict,
        news_items:   list,
    ) -> dict:
        prompt = f"""Analyse this competitor data and produce a structured SWOT + competitive brief.

Competitor: {self.competitor_name}
Our Product: {self.your_product}
Industry: {self.industry}

Website Data: {website_data}
Pricing: {pricing_data}
Reviews: {review_data}
Recent News: {news_items}

Return JSON:
{{
  "summary": "2-sentence overview",
  "strengths":   ["..."],
  "weaknesses":  ["..."],
  "opportunities": ["how we can win against them"],
  "threats":     ["risks they pose to us"],
  "pricing_comparison": "how their pricing compares to ours",
  "win_angles":  ["specific talking points we can use against them in sales"],
  "avoid_in_sales": ["things to avoid when competitor comes up"],
  "overall_threat_level": "low|medium|high"
}}"""

        return await generate_json(prompt, model_type=ModelType.SMART, system_prompt=SWOT_SYSTEM_PROMPT)

    # ── Main run ──────────────────────────────────────────────

    async def run(self) -> dict:
        logger.info(f"[{self.task_id}] Competitor analysis: '{self.competitor_name}' vs '{self.your_product}'")
        await set_task_status(self.task_id, "executing")

        # Run searches concurrently where possible
        website_task = asyncio.create_task(self._get_website_data())
        reviews_task = asyncio.create_task(self._get_review_sentiment())
        news_task    = asyncio.create_task(self._get_recent_news())

        website_data = await website_task
        reviews_data = await reviews_task
        news_items   = await news_task

        # Pricing needs website URL from step 1
        base_url     = website_data.get("website", "")
        pricing_data = await self._get_pricing(base_url) if base_url else {}

        # Final synthesis
        swot = await self._synthesise_swot(website_data, pricing_data, reviews_data, news_items)

        result = {
            "task_id":    self.task_id,
            "goal":       f"Competitor analysis: {self.competitor_name}",
            "agent_type": "competitor_analysis",
            "status":     "completed",
            "output": {
                "summary": swot.get("summary", f"Analysis of {self.competitor_name} complete."),
                "status":  "success",
                "data": {
                    "competitor":       self.competitor_name,
                    "our_product":      self.your_product,
                    "website":          base_url,
                    "product_data":     website_data.get("data", {}),
                    "pricing":          pricing_data,
                    "reviews":          reviews_data,
                    "recent_news":      news_items,
                    "swot":             swot,
                    "threat_level":     swot.get("overall_threat_level", "medium"),
                    "win_angles":       swot.get("win_angles", []),
                },
                "stats": {
                    "sources_checked": 3 + len(news_items),
                    "news_items":      len(news_items),
                },
                "next_steps": [
                    f"Share win_angles with your sales team",
                    f"Monitor {self.competitor_name} with a cron schedule",
                    "Run competitor analysis on their top 3 rivals too",
                ],
            },
            "completed_at": datetime.utcnow().isoformat(),
            "steps_taken":  5,
        }

        await set_task_status(self.task_id, "completed")
        await set_task_result(self.task_id, result)
        logger.info(f"[{self.task_id}] Competitor analysis done. Threat: {swot.get('overall_threat_level')}")
        return result
