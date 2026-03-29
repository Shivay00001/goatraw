"""
GoatRaw — Lead Generation Agent (Complete Use-Case Implementation)
This is the fully wired, production-ready lead gen agent with:
  - Multi-source search (Google, LinkedIn, industry directories)
  - Company website scraping
  - Email finding (Apollo/Hunter/pattern)
  - LinkedIn enrichment
  - Structured output with confidence scores
  - Deduplication
  - CSV export ready
"""

import asyncio
import json
import logging
import re
import uuid
from datetime import datetime
from typing import Optional

from app.services.llm_adapter import generate_json, ModelType
from app.agents.tools import tool_search_web, tool_web_scrape, tool_extract_structured_data
from app.utils.email_finder import tool_find_email, tool_find_domain_emails
from app.utils.linkedin_scraper import tool_linkedin_people_search, tool_linkedin_company_search
from app.core.redis_client import set_task_status, set_task_result, get_redis

logger = logging.getLogger("goatraw.lead_gen")

LEAD_SCHEMA = {
    "company_name": "str",
    "website":      "str",
    "email":        "str",
    "phone":        "str",
    "contact_name": "str",
    "contact_role": "str",
    "linkedin_url": "str",
    "industry":     "str",
    "location":     "str",
    "company_size": "str",
    "description":  "str",
}


class LeadGenAgent:
    """
    Complete lead generation agent.
    Flow:
      1. Search web for companies in niche + location
      2. Scrape each company website
      3. Extract structured data (name, email, phone, description)
      4. Find missing emails via Apollo/Hunter/pattern
      5. LinkedIn enrichment for decision-maker contacts
      6. Deduplicate and score leads
      7. Return structured, ranked list
    """

    def __init__(
        self,
        task_id:    str,
        niche:      str,
        location:   str       = "",
        filters:    dict      = None,
        max_leads:  int       = 20,
        find_emails: bool     = True,
        linkedin_enrich: bool = False,   # Set True if RAPIDAPI_KEY available
    ):
        self.task_id         = task_id
        self.niche           = niche
        self.location        = location
        self.filters         = filters or {}
        self.max_leads       = max_leads
        self.find_emails     = find_emails
        self.linkedin_enrich = linkedin_enrich
        self._leads: list    = []
        self._seen_domains: set = set()

    # ─── Step 1: Multi-source search ─────────────────────────

    async def _search_companies(self) -> list[dict]:
        """Run 3 parallel searches across different query angles."""
        queries = [
            f"{self.niche} companies {self.location} contact email",
            f"top {self.niche} businesses {self.location} website",
            f"best {self.niche} {self.location} services",
        ]
        if self.filters.get("company_size"):
            queries.append(f"{self.filters['company_size']} {self.niche} {self.location}")

        all_results = []
        tasks = [tool_search_web(q, num_results=8) for q in queries]
        search_outputs = await asyncio.gather(*tasks, return_exceptions=True)

        seen_urls = set()
        for output in search_outputs:
            if isinstance(output, Exception):
                continue
            for r in output.get("results", []):
                url = r.get("url", "")
                if url and url not in seen_urls and self._is_valid_company_url(url):
                    seen_urls.add(url)
                    all_results.append(r)

        logger.info(f"[{self.task_id}] Found {len(all_results)} unique URLs from search")
        return all_results[:self.max_leads * 2]  # 2x buffer for filtering

    def _is_valid_company_url(self, url: str) -> bool:
        """Filter out non-company URLs."""
        skip_domains = [
            "linkedin.com", "facebook.com", "twitter.com", "instagram.com",
            "youtube.com", "wikipedia.org", "reddit.com", "yelp.com",
            "glassdoor.com", "indeed.com", "google.com", "bing.com",
            "amazon.com", "quora.com", "medium.com",
        ]
        return not any(d in url for d in skip_domains)

    # ─── Step 2: Scrape company websites ─────────────────────

    async def _scrape_company(self, url: str) -> Optional[dict]:
        """Scrape a company website and extract lead data."""
        domain = re.sub(r"https?://(www\.)?", "", url).split("/")[0]
        if domain in self._seen_domains:
            return None
        self._seen_domains.add(domain)

        page = await tool_web_scrape(url)
        if page.get("status") != "success" or len(page.get("content", "")) < 100:
            return None

        # LLM extraction
        extracted = await tool_extract_structured_data(
            text=page["content"][:5000],
            schema=LEAD_SCHEMA,
        )
        data = extracted.get("data", {})
        if not data or not data.get("company_name"):
            # Fallback: extract from title + content heuristics
            data = self._heuristic_extract(page, url)

        if data:
            data["website"]  = data.get("website") or url
            data["_domain"]  = domain
            data["_raw_url"] = url
        return data if data and data.get("company_name") else None

    def _heuristic_extract(self, page: dict, url: str) -> dict:
        """Regex/heuristic-based extraction when LLM extraction returns nothing."""
        content = page.get("content", "")
        title   = page.get("title", "")

        # Extract emails
        emails  = re.findall(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", content)
        emails  = [e for e in emails if not any(skip in e for skip in ["example", "test", "@2", ".png", ".jpg"])]

        # Extract phone numbers
        phones  = re.findall(r"[\+\(]?[0-9\s\-\(\)]{10,18}", content)
        phones  = [p.strip() for p in phones if len(re.sub(r"\D", "", p)) >= 10]

        domain  = re.sub(r"https?://(www\.)?", "", url).split("/")[0]
        company = title.split("|")[0].split("-")[0].strip() if title else domain

        return {
            "company_name": company[:80],
            "website":      url,
            "email":        emails[0] if emails else None,
            "phone":        phones[0] if phones else None,
            "contact_name": None,
            "contact_role": None,
            "linkedin_url": None,
            "industry":     self.niche,
            "location":     self.location,
            "company_size": None,
            "description":  content[:200],
        }

    # ─── Step 3: Email enrichment ─────────────────────────────

    async def _enrich_email(self, lead: dict) -> dict:
        """Find email if missing."""
        if lead.get("email"):
            return lead

        domain = lead.get("_domain", "")
        if not domain:
            return lead

        # Try domain-level email search first (faster)
        domain_result = await tool_find_domain_emails(domain, num_results=3)
        domain_emails = domain_result.get("emails", [])
        if domain_emails:
            first = domain_emails[0]
            lead["email"] = first.get("email", first) if isinstance(first, dict) else first
            lead["email_source"] = "domain_search"
            return lead

        # Try person-level search if we have a contact name
        if lead.get("contact_name"):
            parts  = lead["contact_name"].split()
            fname  = parts[0] if parts else ""
            lname  = parts[-1] if len(parts) > 1 else ""
            result = await tool_find_email(fname, lname, domain, lead.get("company_name", ""))
            if result.get("email"):
                lead["email"]        = result["email"]
                lead["email_source"] = result["source"]
                lead["email_conf"]   = result["confidence"]

        return lead

    # ─── Step 4: LinkedIn enrichment ─────────────────────────

    async def _enrich_linkedin(self, lead: dict) -> dict:
        """Find decision-maker LinkedIn profiles."""
        company = lead.get("company_name", "")
        if not company or lead.get("linkedin_url"):
            return lead

        result = await tool_linkedin_company_search(company, self.niche, self.location)
        if result.get("status") == "found":
            lead["linkedin_url"]     = result.get("linkedin_url")
            lead["linkedin_data"]    = result.get("snippet", "")

        # Find key decision-makers
        people_result = await tool_linkedin_people_search(
            role=f"CEO OR Founder OR Director OR Manager",
            company=company,
            location=self.location,
            num_results=3,
        )
        people = people_result.get("results", [])
        if people and not lead.get("contact_name"):
            top = people[0]
            lead["contact_name"] = top.get("name", "")
            lead["contact_role"] = top.get("title", "")
            lead["contact_linkedin"] = top.get("linkedin_url", "")

        return lead

    # ─── Step 5: Score and rank ───────────────────────────────

    def _score_lead(self, lead: dict) -> float:
        """Score a lead 0-100 based on data completeness."""
        score = 0
        if lead.get("company_name"): score += 20
        if lead.get("email"):        score += 30
        if lead.get("phone"):        score += 15
        if lead.get("contact_name"): score += 15
        if lead.get("website"):      score += 10
        if lead.get("linkedin_url"): score += 10
        conf = lead.get("email_conf", 1.0)
        if conf < 0.5: score -= 10
        return min(100, score)

    # ─── Main run ─────────────────────────────────────────────

    async def run(self) -> dict:
        logger.info(f"[{self.task_id}] Lead Gen starting: '{self.niche}' in '{self.location}'")
        await set_task_status(self.task_id, "planning")

        # Step 1: Search
        await set_task_status(self.task_id, "executing")
        search_results = await self._search_companies()
        logger.info(f"[{self.task_id}] Scraping {min(len(search_results), self.max_leads)} sites...")

        # Step 2: Scrape concurrently (max 5 at a time)
        urls = [r["url"] for r in search_results[:self.max_leads]]
        scrape_semaphore = asyncio.Semaphore(5)

        async def bounded_scrape(url):
            async with scrape_semaphore:
                return await self._scrape_company(url)

        raw_leads = await asyncio.gather(*[bounded_scrape(u) for u in urls], return_exceptions=True)
        leads = [l for l in raw_leads if l and not isinstance(l, Exception)]
        logger.info(f"[{self.task_id}] Extracted {len(leads)} leads from scraping")

        # Step 3: Email enrichment
        if self.find_emails:
            enrich_sem = asyncio.Semaphore(3)
            async def bounded_enrich(lead):
                async with enrich_sem:
                    return await self._enrich_email(lead)
            leads = await asyncio.gather(*[bounded_enrich(l) for l in leads])

        # Step 4: LinkedIn enrichment (optional, slower)
        if self.linkedin_enrich:
            li_sem = asyncio.Semaphore(2)
            async def bounded_li(lead):
                async with li_sem:
                    return await self._enrich_linkedin(lead)
            leads = list(await asyncio.gather(*[bounded_li(l) for l in leads]))

        # Step 5: Score and clean
        for lead in leads:
            lead["score"] = self._score_lead(lead)
            # Remove internal fields
            lead.pop("_domain",   None)
            lead.pop("_raw_url",  None)

        leads.sort(key=lambda l: l["score"], reverse=True)

        # Build final output
        total_with_email  = sum(1 for l in leads if l.get("email"))
        total_with_phone  = sum(1 for l in leads if l.get("phone"))
        total_with_li     = sum(1 for l in leads if l.get("linkedin_url"))

        result = {
            "task_id":    self.task_id,
            "goal":       f"Lead generation: {self.niche} in {self.location}",
            "agent_type": "lead_generation",
            "status":     "completed",
            "output": {
                "summary": (
                    f"Found {len(leads)} leads in '{self.niche}'"
                    f"{' in ' + self.location if self.location else ''}. "
                    f"{total_with_email} have emails, {total_with_phone} have phone numbers."
                ),
                "status": "success",
                "data":   leads,
                "stats": {
                    "total_leads":     len(leads),
                    "with_email":      total_with_email,
                    "with_phone":      total_with_phone,
                    "with_linkedin":   total_with_li,
                    "avg_score":       round(sum(l["score"] for l in leads) / max(len(leads), 1), 1),
                    "sources_searched": len(search_results),
                },
                "next_steps": [
                    "Export to CSV for outreach",
                    "Run /agent/lead-gen with more specific filters",
                    "Use email_outreach_draft skill to write cold emails",
                    "Import into your CRM",
                ],
                "export_ready": True,
            },
            "completed_at": datetime.utcnow().isoformat(),
            "steps_taken":  5,
        }

        await set_task_status(self.task_id, "completed")
        await set_task_result(self.task_id, result)
        logger.info(f"[{self.task_id}] Lead gen complete: {len(leads)} leads")
        return result
