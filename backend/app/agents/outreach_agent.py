"""
GoatRaw — Outreach Drafting Agent
Generates hyper-personalised multi-channel outreach copy:
  1. Research target company (scrape site, find pain points)
  2. Research decision-maker (LinkedIn, recent news)
  3. Match pain to your value prop
  4. Generate: cold email + follow-up sequence + LinkedIn note + WhatsApp message
  5. Subject line A/B variants
  6. Personalisation tokens highlighted
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from app.services.llm_adapter import generate_json, generate, ModelType
from app.agents.tools          import tool_search_web, tool_web_scrape, tool_extract_structured_data
from app.core.redis_client     import set_task_status, set_task_result

logger = logging.getLogger("goatraw.outreach_agent")

COMPANY_RESEARCH_SCHEMA = {
    "company_name":       "str",
    "industry":           "str",
    "main_product":       "str",
    "target_customer":    "str",
    "recent_news":        "str",
    "tech_stack_hints":   "list[str]",
    "pain_points":        "list[str]",
    "company_size":       "str",
    "funding_stage":      "str",
}

OUTREACH_SYSTEM = """You are a world-class B2B sales copywriter.
Write outreach that:
- Opens with a specific observation about their company (not generic praise)
- States one clear pain point they likely have
- Connects it to a concrete result you deliver
- Has a frictionless CTA (not 'let me know if interested')
- Sounds human — no buzzwords, no AI-speak
Output JSON only."""


class OutreachDraftingAgent:
    def __init__(
        self,
        task_id:        str,
        target_company: str,
        target_person:  str,
        target_role:    str,
        your_product:   str,
        your_value_prop: str,
        channels:       list = None,   # ["email", "linkedin", "whatsapp"]
        company_url:    str  = "",
    ):
        self.task_id         = task_id
        self.target_company  = target_company
        self.target_person   = target_person
        self.target_role     = target_role
        self.your_product    = your_product
        self.your_value_prop = your_value_prop
        self.channels        = channels or ["email", "linkedin"]
        self.company_url     = company_url

    # ── Step 1: Research company ──────────────────────────────

    async def _research_company(self) -> dict:
        """Scrape company website + news to find personalisation hooks."""
        url = self.company_url
        if not url:
            search = await tool_search_web(
                f"{self.target_company} official website",
                num_results=3,
            )
            results = search.get("results", [])
            url     = next((r["url"] for r in results if "linkedin" not in r["url"]), "")

        if not url:
            return {"company_name": self.target_company}

        page    = await tool_web_scrape(url)
        content = page.get("content", "")

        extracted = await tool_extract_structured_data(
            text=content[:5000],
            schema=COMPANY_RESEARCH_SCHEMA,
        )
        data = extracted.get("data", {})
        data["website"] = url

        # Also search for recent news / trigger events
        news = await tool_search_web(
            f"{self.target_company} news announcement hiring fundraising 2025",
            num_results=3,
        )
        trigger_snippets = [r.get("snippet", "") for r in news.get("results", [])[:2]]
        data["trigger_events"] = trigger_snippets

        return data

    # ── Step 2: Research decision-maker ──────────────────────

    async def _research_person(self) -> dict:
        """Find public info about the target person."""
        search = await tool_search_web(
            f"{self.target_person} {self.target_company} {self.target_role} LinkedIn",
            num_results=5,
        )
        results     = search.get("results", [])
        li_result   = next((r for r in results if "linkedin.com/in" in r["url"]), None)
        other_result= next((r for r in results if "linkedin.com" not in r["url"]), None)

        person_data = {
            "name":         self.target_person,
            "role":         self.target_role,
            "company":      self.target_company,
            "linkedin_url": li_result["url"] if li_result else "",
            "bio_snippet":  li_result["snippet"] if li_result else (other_result["snippet"] if other_result else ""),
        }

        # Look for recent posts/content by this person
        content_search = await tool_search_web(
            f'"{self.target_person}" {self.target_company} wrote posted about',
            num_results=3,
        )
        person_data["recent_content"] = [
            r.get("snippet", "") for r in content_search.get("results", [])[:2]
        ]

        return person_data

    # ── Step 3: Generate outreach copy ────────────────────────

    async def _generate_copy(self, company_data: dict, person_data: dict) -> dict:
        """LLM generates personalised outreach for each channel."""

        context = f"""Target Person: {self.target_person}, {self.target_role} at {self.target_company}
Person Bio: {person_data.get('bio_snippet', 'N/A')}
Recent Content: {person_data.get('recent_content', [])}

Company: {self.target_company}
Industry: {company_data.get('industry', 'N/A')}
Main Product: {company_data.get('main_product', 'N/A')}
Company Size: {company_data.get('company_size', 'N/A')}
Recent News/Triggers: {company_data.get('trigger_events', [])}
Likely Pain Points: {company_data.get('pain_points', [])}

Your Product: {self.your_product}
Your Value Prop: {self.your_value_prop}

Channels needed: {self.channels}"""

        prompt = f"""{context}

Generate personalised outreach copy. Return JSON:
{{
  "personalisation_hooks": ["specific observation 1", "observation 2"],
  "identified_pain": "the most likely pain point for this specific person",
  "email": {{
    "subject_a": "subject line variant A (curiosity-based)",
    "subject_b": "subject line variant B (benefit-based)",
    "body": "full email body (150-200 words max)",
    "follow_up_1": "follow-up email for 3 days later (50 words)",
    "follow_up_2": "break-up email for 7 days later (30 words)"
  }},
  "linkedin_note": "connection request note (200 chars max)",
  "linkedin_inmail": "InMail body (300 words max)",
  "whatsapp": "WhatsApp message (under 100 words, conversational)",
  "personalisation_tokens": {{
    "{{company_name}}": "{self.target_company}",
    "{{first_name}}":   "{self.target_person.split()[0]}",
    "{{role}}":         "{self.target_role}",
    "{{pain_point}}":   "detected pain point",
    "{{hook}}":         "personalisation hook"
  }}
}}"""

        return await generate_json(prompt, model_type=ModelType.SMART, system_prompt=OUTREACH_SYSTEM)

    # ── Main run ──────────────────────────────────────────────

    async def run(self) -> dict:
        logger.info(f"[{self.task_id}] Outreach drafting: {self.target_person} @ {self.target_company}")
        await set_task_status(self.task_id, "executing")

        company_task = asyncio.create_task(self._research_company())
        person_task  = asyncio.create_task(self._research_person())

        company_data, person_data = await asyncio.gather(company_task, person_task)
        copy_data = await self._generate_copy(company_data, person_data)

        # Build deliverable output
        channels_generated = [ch for ch in self.channels if ch in ("email", "linkedin", "whatsapp")]

        result = {
            "task_id":    self.task_id,
            "goal":       f"Outreach for {self.target_person} @ {self.target_company}",
            "agent_type": "outreach_drafting",
            "status":     "completed",
            "output": {
                "summary": (
                    f"Generated {len(channels_generated)}-channel outreach for "
                    f"{self.target_person} ({self.target_role}) at {self.target_company}. "
                    f"Personalisation hooks: {len(copy_data.get('personalisation_hooks', []))}"
                ),
                "status": "success",
                "data": {
                    "target": {
                        "person":  self.target_person,
                        "role":    self.target_role,
                        "company": self.target_company,
                    },
                    "research": {
                        "company": company_data,
                        "person":  person_data,
                    },
                    "copy":           copy_data,
                    "channels":       channels_generated,
                    "personalisation_hooks": copy_data.get("personalisation_hooks", []),
                    "identified_pain": copy_data.get("identified_pain", ""),
                },
                "stats": {
                    "channels_generated": len(channels_generated),
                    "email_variants":     2 if "email" in self.channels else 0,
                    "follow_up_sequence": 2 if "email" in self.channels else 0,
                },
                "next_steps": [
                    "Personalise {{tokens}} before sending",
                    "A/B test subject_a vs subject_b",
                    "Schedule follow_up_1 for day 3, follow_up_2 for day 7",
                    "Import to your outreach tool (Apollo, Lemlist, Instantly)",
                ],
                "export_ready": True,
            },
            "completed_at": datetime.utcnow().isoformat(),
            "steps_taken":  4,
        }

        await set_task_status(self.task_id, "completed")
        await set_task_result(self.task_id, result)
        return result
