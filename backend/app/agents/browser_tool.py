"""
GoatRaw - Browser Automation Tool
OpenClaw uses CDP-controlled Chrome. GoatRaw uses Playwright in async mode.
Handles JS-rendered pages, form fills, navigation sequences.
Runs in a sandboxed Docker container on the worker node.
"""

import asyncio
import logging
import os
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger("goatraw.browser")

# Check if playwright is available (not installed in base, optional dep)
try:
    from playwright.async_api import async_playwright, Page, Browser
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("Playwright not installed. Browser tools will be unavailable. pip install playwright")


@dataclass
class BrowserResult:
    url: str
    title: str
    text: str
    html: str
    screenshot_b64: Optional[str] = None
    links: list = None
    status: str = "success"
    error: Optional[str] = None


class GoatRawBrowser:
    """
    Async browser session using Playwright.
    Equivalent to OpenClaw's browser tool with CDP.
    """

    def __init__(self):
        self._browser: Optional[Browser] = None
        self._playwright = None

    async def __aenter__(self):
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError("Playwright not available. Run: pip install playwright && playwright install chromium")
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
            ],
        )
        return self

    async def __aexit__(self, *args):
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def navigate_and_extract(
        self,
        url: str,
        wait_for: str = "load",
        extract_links: bool = False,
        take_screenshot: bool = False,
        timeout_ms: int = 30000,
    ) -> BrowserResult:
        """Navigate to URL and extract page content."""
        if not self._browser:
            raise RuntimeError("Browser not initialized. Use as async context manager.")

        page: Page = await self._browser.new_page()
        try:
            await page.set_extra_http_headers({
                "User-Agent": "Mozilla/5.0 (compatible; GoatRawBot/1.0; +https://goatraw.ai)"
            })
            await page.goto(url, wait_until=wait_for, timeout=timeout_ms)
            await asyncio.sleep(1)  # Brief wait for dynamic content

            title = await page.title()
            text = await page.inner_text("body")
            html = await page.content()

            links = []
            if extract_links:
                anchors = await page.query_selector_all("a[href]")
                for a in anchors[:50]:
                    href = await a.get_attribute("href")
                    link_text = await a.inner_text()
                    if href and href.startswith("http"):
                        links.append({"url": href, "text": link_text.strip()[:100]})

            screenshot_b64 = None
            if take_screenshot:
                import base64
                screenshot_bytes = await page.screenshot(type="png", full_page=False)
                screenshot_b64 = base64.b64encode(screenshot_bytes).decode()

            return BrowserResult(
                url=url,
                title=title,
                text=text[:8000],
                html=html[:10000],
                screenshot_b64=screenshot_b64,
                links=links,
                status="success",
            )

        except Exception as e:
            logger.error(f"Browser navigation failed for {url}: {e}")
            return BrowserResult(url=url, title="", text="", html="", status="error", error=str(e))
        finally:
            await page.close()

    async def fill_form_and_submit(
        self,
        url: str,
        form_data: dict,
        submit_selector: str = 'button[type="submit"]',
    ) -> BrowserResult:
        """Fill and submit a web form."""
        if not self._browser:
            raise RuntimeError("Browser not initialized.")

        page: Page = await self._browser.new_page()
        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)

            for selector, value in form_data.items():
                try:
                    await page.fill(selector, str(value))
                except Exception as e:
                    logger.warning(f"Could not fill {selector}: {e}")

            await page.click(submit_selector)
            await page.wait_for_load_state("networkidle", timeout=15000)

            return BrowserResult(
                url=page.url,
                title=await page.title(),
                text=await page.inner_text("body"),
                html=await page.content(),
                status="success",
            )
        except Exception as e:
            return BrowserResult(url=url, title="", text="", html="", status="error", error=str(e))
        finally:
            await page.close()

    async def scrape_linkedin_profile(self, profile_url: str, cookies: dict = None) -> dict:
        """
        Scrape LinkedIn profile data.
        NOTE: Requires valid session cookies. Use with explicit user consent.
        """
        if not self._browser:
            raise RuntimeError("Browser not initialized.")

        page: Page = await self._browser.new_page()
        try:
            if cookies:
                await page.context.add_cookies([
                    {"name": k, "value": v, "domain": ".linkedin.com", "path": "/"} for k, v in cookies.items()
                ])

            await page.goto(profile_url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)

            text = await page.inner_text("body")
            return {"url": profile_url, "text": text[:5000], "status": "success"}
        except Exception as e:
            return {"url": profile_url, "status": "error", "error": str(e)}
        finally:
            await page.close()


# ─── Tool Function Wrappers ───────────────────────────────────────────────────

async def tool_browser_navigate(url: str, extract_links: bool = False, take_screenshot: bool = False) -> dict:
    """Tool: Navigate to URL using full browser (handles JS-rendered pages)."""
    if not PLAYWRIGHT_AVAILABLE:
        # Fallback to httpx
        from app.agents.tools import tool_web_scrape
        return await tool_web_scrape(url)

    async with GoatRawBrowser() as browser:
        result = await browser.navigate_and_extract(
            url=url,
            extract_links=extract_links,
            take_screenshot=take_screenshot,
        )
        return {
            "url": result.url,
            "title": result.title,
            "content": result.text,
            "links": result.links or [],
            "has_screenshot": result.screenshot_b64 is not None,
            "status": result.status,
            "error": result.error,
        }


async def tool_browser_fill_form(url: str, form_data: dict, submit_selector: str = 'button[type="submit"]') -> dict:
    """Tool: Fill and submit a web form using browser automation."""
    if not PLAYWRIGHT_AVAILABLE:
        return {"status": "error", "error": "Browser automation not available"}

    async with GoatRawBrowser() as browser:
        result = await browser.fill_form_and_submit(url, form_data, submit_selector)
        return {"url": result.url, "title": result.title, "content": result.text[:3000], "status": result.status}
