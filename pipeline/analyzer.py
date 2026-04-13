from __future__ import annotations

from utils.html_cleaner import clean_html, extract_text_content
from utils.page_fetcher import fetch_page
from utils.prompts import PAGE_ANALYZE_PROMPT
from utils.llm import call_text


async def analyze_page(url: str, gemini_key: str = "", openrouter_key: str = "") -> tuple[str, str]:
    """Stage 2: Fetch, clean, and analyze the landing page."""
    raw_html, base_url = fetch_page(url)
    cleaned = clean_html(raw_html, base_url)
    text_content = extract_text_content(cleaned)

    prompt = PAGE_ANALYZE_PROMPT.format(text_content=text_content)
    page_analysis = await call_text(prompt, gemini_key, openrouter_key, max_tokens=4000)

    if not page_analysis:
        raise ValueError("Empty page analysis response")

    return cleaned, page_analysis
