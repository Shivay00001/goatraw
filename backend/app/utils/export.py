"""
GoatRaw — CSV/Excel Export Utility
Converts lead data and other structured task outputs to CSV/XLSX for download.
"""

import csv
import io
import json
import logging
from typing import Any, Union
from datetime import datetime

logger = logging.getLogger("goatraw.export")


def flatten_dict(d: dict, prefix: str = "", sep: str = "_") -> dict:
    """Flatten nested dicts for CSV export."""
    items = {}
    for k, v in d.items():
        key = f"{prefix}{sep}{k}" if prefix else k
        if isinstance(v, dict):
            items.update(flatten_dict(v, key, sep))
        elif isinstance(v, list):
            items[key] = "; ".join(str(i) for i in v[:5])
        else:
            items[key] = v
    return items


def leads_to_csv(leads: list[dict]) -> str:
    """Convert lead list to CSV string."""
    if not leads:
        return "No leads found"

    # Flatten and determine columns
    flat_leads = [flatten_dict(l) for l in leads]
    
    # Priority columns first
    priority_cols = [
        "company_name", "email", "phone", "contact_name", "contact_role",
        "website", "linkedin_url", "industry", "location", "company_size",
        "score", "email_source", "description"
    ]
    all_cols = list({k for l in flat_leads for k in l.keys()})
    cols = [c for c in priority_cols if c in all_cols] + \
           [c for c in all_cols if c not in priority_cols and not c.startswith("_")]

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    writer.writeheader()
    for lead in flat_leads:
        writer.writerow({k: lead.get(k, "") for k in cols})

    return buf.getvalue()


def task_result_to_csv(task_result: dict) -> str:
    """Convert any task result to CSV if data is a list of dicts."""
    output = task_result.get("output", {})
    data   = output.get("data", [])

    if isinstance(data, list) and data:
        if isinstance(data[0], dict):
            return leads_to_csv(data)

    # Fallback: export as key-value pairs
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["field", "value"])
    for k, v in (output or task_result).items():
        writer.writerow([k, json.dumps(v) if isinstance(v, (dict, list)) else v])
    return buf.getvalue()


def format_for_notion(leads: list[dict]) -> list[dict]:
    """Format leads for Notion API import."""
    return [
        {
            "Company":    {"title": [{"text": {"content": l.get("company_name", "")}}]},
            "Email":      {"email": l.get("email")},
            "Phone":      {"phone_number": l.get("phone")},
            "Website":    {"url": l.get("website")},
            "Contact":    {"rich_text": [{"text": {"content": l.get("contact_name", "")}}]},
            "Role":       {"rich_text": [{"text": {"content": l.get("contact_role", "")}}]},
            "LinkedIn":   {"url": l.get("linkedin_url")},
            "Industry":   {"select": {"name": l.get("industry", "Unknown")}},
            "Location":   {"rich_text": [{"text": {"content": l.get("location", "")}}]},
            "Score":      {"number": l.get("score", 0)},
            "Added":      {"date": {"start": datetime.utcnow().date().isoformat()}},
        }
        for l in leads
    ]


def format_for_google_sheets(leads: list[dict]) -> dict:
    """Format leads as Google Sheets append-ready values."""
    headers = [
        "Company", "Email", "Phone", "Contact Name", "Role",
        "Website", "LinkedIn", "Industry", "Location", "Score", "Added"
    ]
    rows = [headers]
    for l in leads:
        rows.append([
            l.get("company_name", ""),
            l.get("email", ""),
            l.get("phone", ""),
            l.get("contact_name", ""),
            l.get("contact_role", ""),
            l.get("website", ""),
            l.get("linkedin_url", ""),
            l.get("industry", ""),
            l.get("location", ""),
            l.get("score", 0),
            datetime.utcnow().date().isoformat(),
        ])
    return {"values": rows}
