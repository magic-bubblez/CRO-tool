from __future__ import annotations

from utils.prompts import AD_EXTRACT_PROMPT
from utils.llm import call_vision


async def extract_ad_info(ad_creative_path: str = "", gemini_key: str = "", groq_key: str = "", openrouter_key: str = "") -> str:
    """Stage 1: Analyze ad creative using vision model."""
    if not ad_creative_path:
        raise ValueError("ad_creative_path must be provided")

    return await call_vision(ad_creative_path, AD_EXTRACT_PROMPT, gemini_key, groq_key, openrouter_key)
