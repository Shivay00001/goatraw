"""
GoatRaw — Extended Tool Registry
Adds email finder, LinkedIn, and notification tools to the base registry.
Call this from tools.py to extend TOOL_REGISTRY.
"""

from app.agents.tools import TOOL_REGISTRY, ToolDefinition
from app.utils.email_finder   import tool_find_email, tool_find_domain_emails
from app.utils.linkedin_scraper import (
    tool_linkedin_company_search,
    tool_linkedin_people_search,
    tool_extract_linkedin_emails,
)
from app.agents.browser_tool import tool_browser_navigate, tool_browser_fill_form


def register_extended_tools():
    """Register all extended tools into the main TOOL_REGISTRY."""

    TOOL_REGISTRY["find_email"] = ToolDefinition(
        name="find_email",
        description="Find a business email for a person at a company using Apollo, Hunter, or pattern guessing.",
        parameters={
            "type": "object",
            "properties": {
                "first_name":      {"type": "string"},
                "last_name":       {"type": "string"},
                "company_domain":  {"type": "string", "description": "e.g. notion.so"},
                "company_name":    {"type": "string"},
            },
            "required": ["first_name", "last_name", "company_domain"],
        },
        fn=tool_find_email,
    )

    TOOL_REGISTRY["find_domain_emails"] = ToolDefinition(
        name="find_domain_emails",
        description="Find all known email addresses for a company domain.",
        parameters={
            "type": "object",
            "properties": {
                "domain":      {"type": "string"},
                "num_results": {"type": "integer", "default": 10},
            },
            "required": ["domain"],
        },
        fn=tool_find_domain_emails,
    )

    TOOL_REGISTRY["linkedin_company_search"] = ToolDefinition(
        name="linkedin_company_search",
        description="Find a company's LinkedIn page and extract public information.",
        parameters={
            "type": "object",
            "properties": {
                "company_name": {"type": "string"},
                "industry":     {"type": "string"},
                "location":     {"type": "string"},
            },
            "required": ["company_name"],
        },
        fn=tool_linkedin_company_search,
    )

    TOOL_REGISTRY["linkedin_people_search"] = ToolDefinition(
        name="linkedin_people_search",
        description="Find people on LinkedIn by role, company, and location.",
        parameters={
            "type": "object",
            "properties": {
                "role":        {"type": "string", "description": "e.g. 'CEO' or 'Marketing Manager'"},
                "company":     {"type": "string"},
                "location":    {"type": "string"},
                "num_results": {"type": "integer", "default": 10},
            },
            "required": ["role"],
        },
        fn=tool_linkedin_people_search,
    )

    TOOL_REGISTRY["browser_navigate"] = ToolDefinition(
        name="browser_navigate",
        description="Navigate to a URL using a full browser (handles JavaScript-rendered pages).",
        parameters={
            "type": "object",
            "properties": {
                "url":             {"type": "string"},
                "extract_links":   {"type": "boolean", "default": False},
                "take_screenshot": {"type": "boolean", "default": False},
            },
            "required": ["url"],
        },
        fn=tool_browser_navigate,
    )

    TOOL_REGISTRY["browser_fill_form"] = ToolDefinition(
        name="browser_fill_form",
        description="Fill and submit a web form using browser automation.",
        parameters={
            "type": "object",
            "properties": {
                "url":              {"type": "string"},
                "form_data":        {"type": "object", "description": "CSS selector → value mapping"},
                "submit_selector":  {"type": "string", "default": "button[type='submit']"},
            },
            "required": ["url", "form_data"],
        },
        fn=tool_browser_fill_form,
    )


# Auto-register when module is imported
register_extended_tools()
