"""
GoatRaw - Tool Registry
All tools available to the agent. Each tool is async and returns structured data.
"""

import httpx
import json
import logging
from typing import Any, Callable, Dict
from dataclasses import dataclass

logger = logging.getLogger("goatraw.tools")


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: dict  # JSON Schema
    fn: Callable


# ─── Tool Implementations ─────────────────────────────────────────────────────

async def tool_web_scrape(url: str, extract_text: bool = True) -> dict:
    """Fetch and extract text content from a URL."""
    try:
        async with httpx.AsyncClient(
            timeout=30,
            headers={"User-Agent": "Mozilla/5.0 (compatible; GoatRawBot/1.0)"},
            follow_redirects=True,
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            html = resp.text

        if extract_text:
            # Basic tag stripping — use BeautifulSoup in production
            import re
            text = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL)
            text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
            return {"url": url, "content": text[:8000], "status": "success"}

        return {"url": url, "content": html[:8000], "status": "success"}
    except Exception as e:
        return {"url": url, "content": "", "status": "error", "error": str(e)}


async def tool_search_web(query: str, num_results: int = 5) -> dict:
    """
    Search the web using SerpAPI or DuckDuckGo fallback.
    Set SERPAPI_KEY env var for production. Falls back to DDG HTML scrape.
    """
    import os
    serpapi_key = os.getenv("SERPAPI_KEY", "")

    if serpapi_key:
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(
                    "https://serpapi.com/search",
                    params={"q": query, "api_key": serpapi_key, "num": num_results},
                )
                data = resp.json()
                results = [
                    {"title": r.get("title"), "url": r.get("link"), "snippet": r.get("snippet")}
                    for r in data.get("organic_results", [])[:num_results]
                ]
                return {"query": query, "results": results, "source": "serpapi"}
        except Exception as e:
            logger.warning(f"SerpAPI failed: {e}, falling back to DDG")

    # DuckDuckGo fallback (HTML scrape)
    try:
        import re
        async with httpx.AsyncClient(
            timeout=20,
            headers={"User-Agent": "Mozilla/5.0"},
            follow_redirects=True,
        ) as client:
            resp = await client.get(
                f"https://html.duckduckgo.com/html/?q={query.replace(' ', '+')}"
            )
            html = resp.text
            titles = re.findall(r'class="result__title"[^>]*>.*?<a[^>]*>(.*?)</a>', html, re.DOTALL)
            urls = re.findall(r'class="result__url"[^>]*>(.*?)</span>', html, re.DOTALL)
            snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)

            results = []
            for i in range(min(num_results, len(titles))):
                results.append({
                    "title": re.sub(r"<[^>]+>", "", titles[i]).strip(),
                    "url": urls[i].strip() if i < len(urls) else "",
                    "snippet": re.sub(r"<[^>]+>", "", snippets[i]).strip() if i < len(snippets) else "",
                })
            return {"query": query, "results": results, "source": "duckduckgo"}
    except Exception as e:
        return {"query": query, "results": [], "error": str(e)}


async def tool_extract_structured_data(text: str, schema: dict) -> dict:
    """Use LLM to extract structured data from raw text according to a schema."""
    from app.services.llm_adapter import generate_json, ModelType

    prompt = f"""Extract structured data from the following text according to this JSON schema:

Schema: {json.dumps(schema, indent=2)}

Text:
{text[:4000]}

Return ONLY valid JSON matching the schema. If a field cannot be found, use null."""

    try:
        result = await generate_json(prompt, model_type=ModelType.FAST)
        return {"data": result, "status": "success"}
    except Exception as e:
        return {"data": {}, "status": "error", "error": str(e)}


async def tool_http_request(url: str, method: str = "GET", headers: dict = None, body: dict = None) -> dict:
    """Make an HTTP request to any external API."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.request(
                method=method.upper(),
                url=url,
                headers=headers or {},
                json=body,
            )
            try:
                data = resp.json()
            except Exception:
                data = {"raw": resp.text[:2000]}
            return {"status_code": resp.status_code, "data": data, "status": "success"}
    except Exception as e:
        return {"status_code": 0, "data": {}, "status": "error", "error": str(e)}


async def tool_summarize_text(text: str, max_length: int = 500) -> dict:
    """Summarize long text using LLM."""
    from app.services.llm_adapter import generate, ModelType
    prompt = f"Summarize the following text in under {max_length} characters. Be concise and factual:\n\n{text[:5000]}"
    summary = await generate(prompt, model_type=ModelType.FAST)
    return {"summary": summary, "status": "success"}


# ─── Tool Registry ────────────────────────────────────────────────────────────

TOOL_REGISTRY: Dict[str, ToolDefinition] = {
    "web_scrape": ToolDefinition(
        name="web_scrape",
        description="Fetch and extract text content from a URL.",
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to scrape"},
                "extract_text": {"type": "boolean", "default": True},
            },
            "required": ["url"],
        },
        fn=tool_web_scrape,
    ),
    "search_web": ToolDefinition(
        name="search_web",
        description="Search the web for information using a query string.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "num_results": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
        fn=tool_search_web,
    ),
    "extract_structured_data": ToolDefinition(
        name="extract_structured_data",
        description="Extract structured data from text using a JSON schema.",
        parameters={
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "schema": {"type": "object"},
            },
            "required": ["text", "schema"],
        },
        fn=tool_extract_structured_data,
    ),
    "http_request": ToolDefinition(
        name="http_request",
        description="Make an HTTP request to an external API endpoint.",
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "method": {"type": "string", "enum": ["GET", "POST", "PUT", "DELETE"]},
                "headers": {"type": "object"},
                "body": {"type": "object"},
            },
            "required": ["url"],
        },
        fn=tool_http_request,
    ),
    "summarize_text": ToolDefinition(
        name="summarize_text",
        description="Summarize a long piece of text.",
        parameters={
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "max_length": {"type": "integer", "default": 500},
            },
            "required": ["text"],
        },
        fn=tool_summarize_text,
    ),
}


async def execute_tool(tool_name: str, params: dict) -> Any:
    """Execute a registered tool by name with given params."""
    if tool_name not in TOOL_REGISTRY:
        return {"error": f"Unknown tool: {tool_name}", "status": "error"}

    tool = TOOL_REGISTRY[tool_name]
    logger.info(f"Executing tool: {tool_name} | params: {list(params.keys())}")
    return await tool.fn(**params)


def get_tool_descriptions() -> str:
    """Return tool descriptions formatted for LLM prompt injection."""
    lines = []
    for name, tool in TOOL_REGISTRY.items():
        lines.append(f"- {name}: {tool.description}")
        lines.append(f"  Parameters: {json.dumps(tool.parameters['properties'])}")
    return "\n".join(lines)
