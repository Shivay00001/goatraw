"""
GoatRaw — Email Finder Tool
Finds business email addresses for a person/company using multiple sources:
  1. Apollo.io API (best, needs key)
  2. Hunter.io API (good, needs key)
  3. Domain pattern + verification fallback
"""

import httpx
import logging
import re
import os
from typing import Optional

logger = logging.getLogger("goatraw.email_finder")

APOLLO_KEY  = os.getenv("APOLLO_API_KEY", "")
HUNTER_KEY  = os.getenv("HUNTER_API_KEY", "")

COMMON_PATTERNS = [
    "{first}@{domain}",
    "{first}.{last}@{domain}",
    "{f}{last}@{domain}",
    "{first}{last}@{domain}",
    "contact@{domain}",
    "info@{domain}",
    "hello@{domain}",
    "sales@{domain}",
]


async def find_email_apollo(first_name: str, last_name: str, company_domain: str) -> Optional[str]:
    """Use Apollo.io People Match API to find email."""
    if not APOLLO_KEY:
        return None
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://api.apollo.io/v1/people/match",
                json={
                    "first_name": first_name,
                    "last_name": last_name,
                    "domain": company_domain,
                    "reveal_personal_emails": False,
                },
                headers={"X-Api-Key": APOLLO_KEY, "Content-Type": "application/json"},
            )
            data = resp.json()
            person = data.get("person", {})
            email = person.get("email") or person.get("work_email")
            if email and "@" in email:
                logger.info(f"Apollo found: {email}")
                return email
    except Exception as e:
        logger.warning(f"Apollo API failed: {e}")
    return None


async def find_email_hunter(first_name: str, last_name: str, company_domain: str) -> Optional[str]:
    """Use Hunter.io Email Finder API."""
    if not HUNTER_KEY:
        return None
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://api.hunter.io/v2/email-finder",
                params={
                    "domain":      company_domain,
                    "first_name":  first_name,
                    "last_name":   last_name,
                    "api_key":     HUNTER_KEY,
                },
            )
            data = resp.json()
            email = data.get("data", {}).get("email")
            score = data.get("data", {}).get("score", 0)
            if email and score >= 50:
                logger.info(f"Hunter found: {email} (score {score})")
                return email
    except Exception as e:
        logger.warning(f"Hunter.io API failed: {e}")
    return None


async def verify_email_format(email: str) -> bool:
    """Basic email format check (no SMTP ping — avoids spam flags)."""
    pattern = r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


async def guess_email_patterns(first_name: str, last_name: str, domain: str) -> list[str]:
    """Generate common email pattern guesses for a person."""
    first = first_name.lower().strip()
    last  = last_name.lower().strip()
    f     = first[0] if first else ""

    candidates = []
    for pattern in COMMON_PATTERNS:
        email = pattern.format(first=first, last=last, f=f, domain=domain)
        if await verify_email_format(email):
            candidates.append(email)
    return candidates


async def tool_find_email(
    first_name: str,
    last_name: str,
    company_domain: str,
    company_name: str = "",
) -> dict:
    """
    Master email finder tool.
    Tries Apollo → Hunter → pattern guesses.
    Returns best candidate with confidence score.
    """
    domain = company_domain.lower().strip().removeprefix("https://").removeprefix("http://").removeprefix("www.").rstrip("/")

    logger.info(f"Finding email for {first_name} {last_name} @ {domain}")

    # Try Apollo first (most accurate)
    email = await find_email_apollo(first_name, last_name, domain)
    if email:
        return {"email": email, "source": "apollo", "confidence": 0.95, "status": "found"}

    # Try Hunter
    email = await find_email_hunter(first_name, last_name, domain)
    if email:
        return {"email": email, "source": "hunter", "confidence": 0.85, "status": "found"}

    # Fallback to pattern guesses
    candidates = await guess_email_patterns(first_name, last_name, domain)
    if candidates:
        best_guess = candidates[0]  # Most common pattern: first@domain
        return {
            "email": best_guess,
            "source": "pattern_guess",
            "confidence": 0.35,
            "alternatives": candidates[1:4],
            "status": "guessed",
            "note": "Low confidence. Verify before sending.",
        }

    return {
        "email": None,
        "source": "none",
        "confidence": 0.0,
        "status": "not_found",
        "domain_tried": domain,
    }


async def tool_find_domain_emails(domain: str, num_results: int = 10) -> dict:
    """
    Find all known emails for a domain using Hunter Domain Search.
    Great for finding generic contact@, info@, sales@ addresses.
    """
    if not HUNTER_KEY:
        # Scrape-based fallback
        from app.agents.tools import tool_web_scrape
        result = await tool_web_scrape(f"https://{domain}/contact")
        emails = re.findall(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", result.get("content", ""))
        emails = list(set(e for e in emails if domain in e))[:num_results]
        return {"domain": domain, "emails": emails, "source": "scrape", "count": len(emails)}

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://api.hunter.io/v2/domain-search",
                params={"domain": domain, "limit": num_results, "api_key": HUNTER_KEY},
            )
            data = resp.json()
            emails = [
                {"email": e["value"], "type": e.get("type"), "confidence": e.get("confidence")}
                for e in data.get("data", {}).get("emails", [])
            ]
            return {"domain": domain, "emails": emails, "source": "hunter", "count": len(emails)}
    except Exception as e:
        return {"domain": domain, "emails": [], "source": "error", "error": str(e)}
