"""
GoatRaw — LinkedIn Scraper Tool
Scrapes LinkedIn company/people pages.
Uses:
  1. RapidAPI LinkedIn scraper (needs key)
  2. Scrapin.io API (needs key)
  3. Google SERP-based LinkedIn search fallback
NOTE: Always comply with LinkedIn ToS and robots.txt.
      This tool is for legitimate business research only.
"""

import httpx
import logging
import os
import re
from typing import Optional

logger = logging.getLogger("goatraw.linkedin")

RAPIDAPI_KEY  = os.getenv("RAPIDAPI_KEY", "")
SCRAPIN_KEY   = os.getenv("SCRAPIN_API_KEY", "")
SERPAPI_KEY   = os.getenv("SERPAPI_KEY", "")


async def scrape_linkedin_company_rapidapi(company_url: str) -> dict:
    """Use RapidAPI's LinkedIn scraper endpoint."""
    if not RAPIDAPI_KEY:
        return {}
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                "https://linkedin-data-scraper.p.rapidapi.com/company",
                params={"url": company_url},
                headers={
                    "X-RapidAPI-Key":  RAPIDAPI_KEY,
                    "X-RapidAPI-Host": "linkedin-data-scraper.p.rapidapi.com",
                },
            )
            if resp.status_code == 200:
                return resp.json()
    except Exception as e:
        logger.warning(f"RapidAPI LinkedIn failed: {e}")
    return {}


async def search_linkedin_via_google(query: str, num_results: int = 5) -> list[dict]:
    """
    Search LinkedIn profiles/companies via Google SERP (site:linkedin.com).
    No LinkedIn auth needed — uses public search.
    """
    from app.agents.tools import tool_search_web
    results = await tool_search_web(f"site:linkedin.com {query}", num_results=num_results)
    linkedin_results = []
    for r in results.get("results", []):
        url = r.get("url", "")
        if "linkedin.com" in url:
            linkedin_results.append({
                "title":   r.get("title", ""),
                "url":     url,
                "snippet": r.get("snippet", ""),
            })
    return linkedin_results


async def tool_linkedin_company_search(
    company_name: str,
    industry: str = "",
    location: str = "",
) -> dict:
    """
    Find a company's LinkedIn page and extract public info.
    Returns: name, industry, size, website, description, key_people.
    """
    # Try direct Google search for the LinkedIn company page
    query = f"{company_name} {industry} {location} LinkedIn company".strip()
    results = await search_linkedin_via_google(query, num_results=3)

    company_urls = [
        r["url"] for r in results
        if "linkedin.com/company/" in r["url"]
    ]

    if not company_urls:
        return {
            "company": company_name,
            "linkedin_url": None,
            "status": "not_found",
            "results": results,
        }

    best_url = company_urls[0]

    # If RapidAPI available, get full data
    if RAPIDAPI_KEY:
        data = await scrape_linkedin_company_rapidapi(best_url)
        if data:
            return {
                "company":     company_name,
                "linkedin_url": best_url,
                "data":        data,
                "source":      "rapidapi",
                "status":      "found",
            }

    # Fallback: scrape public page
    from app.agents.tools import tool_web_scrape
    page = await tool_web_scrape(best_url)
    content = page.get("content", "")

    # Extract basic info from page text
    size_match = re.search(r"(\d[\d,]+)\s*(?:employees|followers)", content)
    size = size_match.group(0) if size_match else "unknown"

    return {
        "company":     company_name,
        "linkedin_url": best_url,
        "page_title":  page.get("title" if hasattr(page, "get") else "title", ""),
        "employee_count": size,
        "snippet":     content[:500],
        "source":      "scrape",
        "status":      "found",
    }


async def tool_linkedin_people_search(
    role: str,
    company: str = "",
    location: str = "",
    num_results: int = 10,
) -> dict:
    """
    Find people on LinkedIn by role + company + location.
    Returns list of public profile info.
    """
    query = f'site:linkedin.com/in "{role}"'
    if company:
        query += f' "{company}"'
    if location:
        query += f" {location}"

    results = await search_linkedin_via_google(query, num_results=num_results)
    people  = []

    for r in results:
        url     = r.get("url", "")
        title   = r.get("title", "")
        snippet = r.get("snippet", "")

        # Parse name and role from title: "Name - Role at Company | LinkedIn"
        name, job_title, company_found = "", "", ""
        if " - " in title:
            parts      = title.split(" - ", 1)
            name       = parts[0].strip()
            role_part  = parts[1].split(" | ")[0].strip()
            if " at " in role_part:
                role_split    = role_part.split(" at ", 1)
                job_title     = role_split[0].strip()
                company_found = role_split[1].strip()
            else:
                job_title = role_part

        people.append({
            "name":        name or title,
            "title":       job_title,
            "company":     company_found or company,
            "linkedin_url": url,
            "snippet":     snippet[:200],
        })

    return {
        "query":   query,
        "results": people,
        "count":   len(people),
        "status":  "success",
    }


async def tool_extract_linkedin_emails(linkedin_url: str) -> dict:
    """
    Try to find contact email associated with a LinkedIn profile.
    Uses Apollo/Hunter enrichment if profile info is available.
    """
    from app.agents.tools import tool_web_scrape
    from app.utils.email_finder import tool_find_email

    # Scrape the public LinkedIn page for any leaked email
    page    = await tool_web_scrape(linkedin_url)
    content = page.get("content", "")

    # Direct email extraction from page
    emails = re.findall(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", content)
    emails = [e for e in emails if "linkedin" not in e and "example" not in e]

    if emails:
        return {"emails": emails, "source": "direct", "linkedin_url": linkedin_url}

    # Try Apollo enrichment using URL
    if os.getenv("APOLLO_API_KEY"):
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    "https://api.apollo.io/v1/people/match",
                    json={"linkedin_url": linkedin_url},
                    headers={"X-Api-Key": os.getenv("APOLLO_API_KEY", "")},
                )
                data  = resp.json()
                email = data.get("person", {}).get("email")
                if email:
                    return {"emails": [email], "source": "apollo", "linkedin_url": linkedin_url}
        except Exception as e:
            logger.warning(f"Apollo enrichment failed: {e}")

    return {"emails": [], "source": "not_found", "linkedin_url": linkedin_url}
