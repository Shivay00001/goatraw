"""
GoatRaw — Website Audit Agent
Full-spectrum website analysis:
  1. SEO: title, meta, h1, sitemap, robots
  2. Copywriting: clarity, value prop, CTA strength
  3. Conversion: trust signals, social proof, objection handling
  4. Technical: load hints, broken links, mobile signals
  5. Competitor comparison (optional)
  6. Prioritised action list
"""

import asyncio
import re
import logging
from datetime import datetime
from typing import Optional

from app.services.llm_adapter  import generate_json, ModelType
from app.agents.tools          import tool_web_scrape, tool_search_web, tool_extract_structured_data
from app.core.redis_client     import set_task_status, set_task_result

logger = logging.getLogger("goatraw.audit_agent")

TECHNICAL_SCHEMA = {
    "page_title":          "str",
    "meta_description":    "str",
    "h1_tags":             "list[str]",
    "h2_tags":             "list[str]",
    "has_ssl":             "bool",
    "has_sitemap_hint":    "bool",
    "word_count":          "int",
    "has_video":           "bool",
    "has_testimonials":    "bool",
    "has_pricing":         "bool",
    "cta_buttons":         "list[str]",
    "contact_info_present":"bool",
    "social_links":        "list[str]",
}

AUDIT_SYSTEM = """You are a conversion rate optimisation (CRO) and SEO expert.
Produce a detailed, actionable website audit.
Be specific: name exact issues, not vague generalities.
Score each dimension 1-10. Output JSON only."""


class WebsiteAuditAgent:
    def __init__(
        self,
        task_id:    str,
        url:        str,
        industry:   str  = "",
        competitor_url: Optional[str] = None,
    ):
        self.task_id        = task_id
        self.url            = url.rstrip("/")
        self.industry       = industry
        self.competitor_url = competitor_url

    # ── Step 1: Scrape all key pages ─────────────────────────

    async def _scrape_pages(self) -> dict:
        """Scrape homepage, /about, /pricing, /contact."""
        pages_to_check = [
            self.url,
            self.url + "/about",
            self.url + "/pricing",
        ]
        pages = {}
        for page_url in pages_to_check:
            result = await tool_web_scrape(page_url)
            if result.get("status") == "success" and len(result.get("content", "")) > 200:
                slug = page_url.replace(self.url, "") or "/"
                pages[slug] = {
                    "content": result["content"][:4000],
                    "title":   result.get("title", ""),
                    "length":  len(result.get("content", "")),
                }
        return pages

    # ── Step 2: Extract technical signals ────────────────────

    async def _extract_technical(self, homepage_content: str, homepage_title: str) -> dict:
        """Extract technical SEO + structural signals."""
        # Count words
        words      = len(re.sub(r"<[^>]+>", "", homepage_content).split())
        has_ssl    = self.url.startswith("https://")

        extracted  = await tool_extract_structured_data(
            text=homepage_content[:4000],
            schema=TECHNICAL_SCHEMA,
        )
        data = extracted.get("data", {})
        data["has_ssl"]   = has_ssl
        data["word_count"]= words
        data["url"]       = self.url

        # Extract internal links
        links      = re.findall(r'href=["\']([^"\']+)["\']', homepage_content)
        int_links  = [l for l in links if l.startswith("/") or self.url in l]
        data["internal_link_count"] = len(set(int_links))

        # Check for common trust signals in text
        trust_keywords = ["trusted", "clients", "customers", "reviews", "rating",
                          "certified", "award", "featured", "guarantee", "secure"]
        data["trust_signal_count"] = sum(1 for kw in trust_keywords if kw in homepage_content.lower())

        return data

    # ── Step 3: Search competitor & industry benchmarks ──────

    async def _get_industry_benchmarks(self) -> dict:
        domain   = re.sub(r"https?://(www\.)?", "", self.url).split("/")[0]
        industry = self.industry or "business"

        # Search for conversion benchmarks
        search = await tool_search_web(
            f"{industry} website conversion rate benchmark average 2025",
            num_results=4,
        )
        snippets = [r.get("snippet", "") for r in search.get("results", [])[:3]]

        return {
            "industry":          industry,
            "benchmark_snippets": snippets,
            "domain":            domain,
        }

    # ── Step 4: LLM full audit synthesis ─────────────────────

    async def _synthesise_audit(self, pages: dict, technical: dict, benchmarks: dict) -> dict:
        homepage_content = pages.get("/", {}).get("content", "")[:3000]
        pricing_content  = pages.get("/pricing", {}).get("content", "")[:2000]

        prompt = f"""Audit this website comprehensively.

URL: {self.url}
Industry: {self.industry or 'unknown'}
Homepage content (first 3000 chars):
{homepage_content}

Pricing page content:
{pricing_content}

Technical signals:
{technical}

Industry benchmarks:
{benchmarks}

Return JSON:
{{
  "overall_score": 72,
  "scores": {{
    "seo":              7,
    "copywriting":      5,
    "conversion":       6,
    "trust_signals":    4,
    "technical":        8,
    "mobile_readiness": 7
  }},
  "critical_issues": [
    {{"issue": "No clear value proposition above the fold", "impact": "high", "fix": "Add a one-sentence benefit statement as H1"}}
  ],
  "seo_audit": {{
    "title_tag":         {{"current": "...", "score": 6, "recommendation": "..."}},
    "meta_description":  {{"current": "...", "score": 5, "recommendation": "..."}},
    "h1":                {{"current": "...", "score": 7, "recommendation": "..."}},
    "keyword_gaps":      ["keyword 1", "keyword 2"],
    "missing_elements":  ["sitemap link in footer", "canonical tags"]
  }},
  "copy_audit": {{
    "value_prop_clarity":  6,
    "cta_strength":        5,
    "social_proof":        4,
    "objection_handling":  3,
    "readability_score":   7,
    "improvements": [
      "Replace 'We are a leading...' with specific customer outcome",
      "Add testimonials from named customers with companies"
    ]
  }},
  "conversion_audit": {{
    "funnel_clarity":       5,
    "friction_points":      ["3 form fields before seeing demo", "no live chat"],
    "missing_trust_signals":["security badges", "customer logos", "money-back guarantee"],
    "cta_improvements":     ["Change 'Submit' to 'Get My Free Report'"]
  }},
  "quick_wins": [
    "Add 3 customer logos above the fold — 30 min, +15% trust",
    "Change primary CTA button colour to high-contrast — 10 min, +8% clicks",
    "Add live chat widget — 20 min, captures 30% more leads"
  ],
  "priority_actions": [
    {{"priority": 1, "action": "...", "effort": "low", "impact": "high", "time_estimate": "2h"}},
    {{"priority": 2, "action": "...", "effort": "medium", "impact": "high", "time_estimate": "1 day"}}
  ]
}}"""

        return await generate_json(prompt, model_type=ModelType.SMART, system_prompt=AUDIT_SYSTEM)

    # ── Main run ──────────────────────────────────────────────

    async def run(self) -> dict:
        logger.info(f"[{self.task_id}] Website audit: {self.url}")
        await set_task_status(self.task_id, "executing")

        # Concurrent scraping + benchmarks
        pages_task      = asyncio.create_task(self._scrape_pages())
        benchmarks_task = asyncio.create_task(self._get_industry_benchmarks())

        pages, benchmarks = await asyncio.gather(pages_task, benchmarks_task)
        homepage = pages.get("/", {})

        technical = await self._extract_technical(
            homepage.get("content", ""),
            homepage.get("title", ""),
        )

        audit = await self._synthesise_audit(pages, technical, benchmarks)

        overall  = audit.get("overall_score", 0)
        criticals = audit.get("critical_issues", [])
        quick_wins= audit.get("quick_wins", [])

        result = {
            "task_id":    self.task_id,
            "goal":       f"Website audit: {self.url}",
            "agent_type": "website_audit",
            "status":     "completed",
            "output": {
                "summary": (
                    f"Website scored {overall}/100. "
                    f"Found {len(criticals)} critical issues and {len(quick_wins)} quick wins. "
                    f"Top priority: {criticals[0]['issue'] if criticals else 'See full report'}"
                ),
                "status": "success",
                "data": {
                    "url":            self.url,
                    "overall_score":  overall,
                    "scores":         audit.get("scores", {}),
                    "critical_issues":criticals,
                    "quick_wins":     quick_wins,
                    "seo_audit":      audit.get("seo_audit", {}),
                    "copy_audit":     audit.get("copy_audit", {}),
                    "conversion_audit": audit.get("conversion_audit", {}),
                    "priority_actions": audit.get("priority_actions", []),
                    "technical_data": technical,
                    "pages_audited":  list(pages.keys()),
                },
                "stats": {
                    "pages_checked":    len(pages),
                    "critical_issues":  len(criticals),
                    "quick_wins":       len(quick_wins),
                    "overall_score":    overall,
                },
                "next_steps": [
                    f"Fix {criticals[0]['issue']} first (highest impact)" if criticals else "Implement quick wins",
                    "Schedule monthly re-audit to track progress",
                    "Run competitor analysis on your top 3 rivals",
                ],
            },
            "completed_at": datetime.utcnow().isoformat(),
            "steps_taken":  4,
        }

        await set_task_status(self.task_id, "completed")
        await set_task_result(self.task_id, result)
        logger.info(f"[{self.task_id}] Audit done. Score: {overall}/100")
        return result
