"""
GoatRaw — Monitoring Agent
Continuous change-detection agent. Runs on schedule via cron system.
Tracks: web pages, keywords, competitor prices, news, GitHub repos.
Only fires notification when something ACTUALLY changes (SmartMonitor).
"""

import asyncio
import hashlib
import json
import logging
from datetime import datetime
from typing import Optional

from app.services.llm_adapter  import generate_json, ModelType
from app.agents.tools          import tool_search_web, tool_web_scrape
from app.core.redis_client     import get_redis, set_task_status, set_task_result
from app.agents.orchestrator_v2 import SmartMonitor

logger = logging.getLogger("goatraw.monitor_agent")

smart_monitor = SmartMonitor()


class MonitoringAgent:
    """
    Runs on a schedule (cron). Checks for changes.
    Uses SmartMonitor to suppress redundant notifications.
    """

    MONITOR_TYPES = {
        "keyword_news":      "Monitor news + search results for a keyword",
        "competitor_price":  "Track a competitor's pricing page for changes",
        "url_change":        "Detect content changes on any URL",
        "github_releases":   "Track new releases for a GitHub repository",
        "job_postings":      "Monitor a company's job postings",
        "funding_news":      "Track funding announcements in an industry",
    }

    def __init__(
        self,
        task_id:       str,
        monitor_type:  str,
        target:        str,        # keyword / URL / company name / GitHub repo
        user_id:       str,
        context:       dict = None,
    ):
        self.task_id      = task_id
        self.monitor_type = monitor_type
        self.target       = target
        self.user_id      = user_id
        self.context      = context or {}

    # ── Monitor implementations ───────────────────────────────

    async def _monitor_keyword_news(self) -> dict:
        """Search for recent news about a keyword."""
        results = await tool_search_web(
            f"{self.target} news latest 2025",
            num_results=10,
        )
        items = results.get("results", [])
        return {
            "type":    "keyword_news",
            "keyword": self.target,
            "items":   items[:8],
            "count":   len(items),
        }

    async def _monitor_competitor_price(self) -> dict:
        """Scrape and extract pricing from a competitor's pricing page."""
        # Try /pricing endpoint first
        url      = self.target.rstrip("/")
        if not url.startswith("http"):
            url = f"https://{url}"

        pricing_url = url + "/pricing"
        page        = await tool_web_scrape(pricing_url)

        if page.get("status") != "success":
            page = await tool_web_scrape(url)

        content = page.get("content", "")

        # Extract pricing info
        prices = []
        # Match common price patterns: $29, $99/mo, ₹2999/month
        import re
        price_matches = re.findall(r"[\$₹€£][\d,]+(?:\.\d{2})?(?:\s*/\s*(?:mo|month|year|yr))?", content)
        prices = list(set(price_matches))[:10]

        return {
            "type":    "competitor_price",
            "url":     pricing_url,
            "prices":  prices,
            "content": content[:1000],
            "scraped_at": datetime.utcnow().isoformat(),
        }

    async def _monitor_url_change(self) -> dict:
        """Detect content changes on a URL."""
        url  = self.target if self.target.startswith("http") else f"https://{self.target}"
        page = await tool_web_scrape(url)

        # Get meaningful content hash (strip timestamps/dynamic elements)
        import re
        content = page.get("content", "")
        # Remove dates and numbers that change naturally
        normalized = re.sub(r"\d{4}-\d{2}-\d{2}", "", content)
        normalized = re.sub(r"\d+\s*(hours?|minutes?|days?)\s*ago", "", normalized)

        return {
            "type":           "url_change",
            "url":            url,
            "content":        content[:1500],
            "content_length": len(content),
            "normalized_hash": hashlib.md5(normalized[:3000].encode()).hexdigest(),
        }

    async def _monitor_github_releases(self) -> dict:
        """Check for new GitHub releases."""
        repo = self.target.replace("https://github.com/", "").strip("/")
        result = await tool_web_scrape(f"https://github.com/{repo}/releases")
        content = result.get("content", "")

        import re
        # Extract release tags
        tags = re.findall(r"v?\d+\.\d+\.?\d*(?:-\w+)?", content)
        tags = list(dict.fromkeys(tags))[:5]   # Deduplicated, ordered

        return {
            "type":          "github_releases",
            "repo":          repo,
            "latest_tags":   tags,
            "page_content":  content[:800],
        }

    async def _monitor_job_postings(self) -> dict:
        """Track company job postings."""
        search = await tool_search_web(
            f"{self.target} jobs hiring 2025 site:linkedin.com OR site:greenhouse.io OR site:lever.co",
            num_results=10,
        )
        jobs = search.get("results", [])

        # Also check company careers page directly
        domain = self.target.lower().replace(" ", "") + ".com"
        careers_urls = [f"https://{domain}/careers", f"https://{domain}/jobs"]

        for url in careers_urls:
            page = await tool_web_scrape(url)
            if page.get("status") == "success" and len(page.get("content", "")) > 200:
                jobs.append({"url": url, "title": page.get("title", ""), "snippet": page["content"][:300]})
                break

        return {
            "type":    "job_postings",
            "company": self.target,
            "jobs":    jobs[:10],
            "count":   len(jobs),
        }

    async def _monitor_funding_news(self) -> dict:
        """Track funding announcements in an industry."""
        results = await tool_search_web(
            f"{self.target} startup raised funding Series 2025",
            num_results=10,
        )
        items = results.get("results", [])
        funding_items = [
            r for r in items
            if any(kw in r.get("title", "").lower() + r.get("snippet", "").lower()
                   for kw in ["raised", "funding", "series", "million", "billion", "seed"])
        ]

        return {
            "type":     "funding_news",
            "industry": self.target,
            "items":    funding_items[:8],
            "count":    len(funding_items),
        }

    # ── Summarise changes ─────────────────────────────────────

    async def _summarise_changes(self, current_data: dict, changed: bool) -> dict:
        """Use LLM to generate a human-readable change summary."""
        if not changed:
            return {
                "changed": False,
                "summary": f"No changes detected in {self.monitor_type}: {self.target}",
                "action_needed": False,
            }

        prompt = f"""Summarise what changed or what was found in this monitoring result.
Monitor type: {self.monitor_type}
Target: {self.target}
Current data: {json.dumps(current_data, default=str)[:2000]}

Return JSON:
{{
  "changed": true,
  "summary": "1-2 sentence plain English summary of what was found/changed",
  "action_needed": true/false,
  "key_findings": ["finding 1", "finding 2"],
  "recommended_action": "what to do about this"
}}"""

        try:
            return await generate_json(prompt, model_type=ModelType.FAST)
        except Exception:
            return {
                "changed": True,
                "summary": f"Change detected in {self.monitor_type}: {self.target}",
                "action_needed": True,
                "key_findings":  [],
            }

    # ── Main run ──────────────────────────────────────────────

    async def run(self) -> dict:
        logger.info(f"[{self.task_id}] Monitor: {self.monitor_type} → {self.target}")
        await set_task_status(self.task_id, "executing")

        # Dispatch to correct monitor
        monitor_fns = {
            "keyword_news":     self._monitor_keyword_news,
            "competitor_price": self._monitor_competitor_price,
            "url_change":       self._monitor_url_change,
            "github_releases":  self._monitor_github_releases,
            "job_postings":     self._monitor_job_postings,
            "funding_news":     self._monitor_funding_news,
        }

        fn = monitor_fns.get(self.monitor_type, self._monitor_keyword_news)
        current_data = await fn()

        # Check if content actually changed since last run
        monitor_id = hashlib.md5(f"{self.monitor_type}:{self.target}".encode()).hexdigest()[:12]
        changed    = await smart_monitor.check_and_notify(monitor_id, current_data, self.user_id)

        # Summarise
        change_summary = await self._summarise_changes(current_data, changed)

        result = {
            "task_id":    self.task_id,
            "goal":       f"Monitor {self.monitor_type}: {self.target}",
            "agent_type": "monitoring",
            "status":     "completed",
            "output": {
                "summary": change_summary.get("summary", "Monitor check complete."),
                "status":  "success",
                "data": {
                    "monitor_type":      self.monitor_type,
                    "target":            self.target,
                    "changed":           changed,
                    "current_data":      current_data,
                    "key_findings":      change_summary.get("key_findings", []),
                    "action_needed":     change_summary.get("action_needed", False),
                    "recommended_action":change_summary.get("recommended_action", ""),
                    "checked_at":        datetime.utcnow().isoformat(),
                },
                "stats": {
                    "changed":      changed,
                    "items_found":  current_data.get("count", 1),
                },
                "next_steps": [
                    change_summary.get("recommended_action", "Review findings"),
                ] if changed else ["No action needed — no changes detected"],
            },
            "completed_at": datetime.utcnow().isoformat(),
            "steps_taken":  3,
        }

        await set_task_status(self.task_id, "completed")
        await set_task_result(self.task_id, result)
        return result
