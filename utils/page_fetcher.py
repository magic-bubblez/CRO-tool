from __future__ import annotations

import asyncio
from urllib.parse import urlparse
from playwright.async_api import async_playwright


async def fetch_page_async(url: str) -> tuple[str, str]:
    """Fetch fully rendered HTML from a URL using a headless browser.

    Executes JavaScript, waits for network idle, returns the final DOM.
    Returns (html_content, base_url).
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )

        await page.goto(url, wait_until="networkidle", timeout=30000)
        # Give extra time for late-loading elements
        await page.wait_for_timeout(2000)

        html = await page.content()
        await browser.close()

    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"

    return html, base_url


def fetch_page(url: str) -> tuple[str, str]:
    """Sync wrapper for fetch_page_async."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # We're inside an async context — run in a thread to avoid blocking
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, fetch_page_async(url))
            return future.result()
    else:
        return asyncio.run(fetch_page_async(url))
