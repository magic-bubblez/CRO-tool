from __future__ import annotations

import asyncio
from pipeline.extractor import extract_ad_info
from pipeline.analyzer import analyze_page
from pipeline.strategist import create_strategy
from pipeline.applier import apply_modifications


async def run_pipeline(
    url: str,
    gemini_key: str,
    groq_key: str = "",
    openrouter_key: str = "",
    ad_creative_path: str = "",
) -> dict:
    """Run the full CRO enhancement pipeline.

    Stages 1 and 2 run in parallel (independent).
    Stage 3 waits for both.
    Stage 4 waits for Stage 3.

    Returns {original_html, enhanced_html, report}.
    """
    # Stage 1: Extract ad info
    ad_analysis = await extract_ad_info(
        ad_creative_path=ad_creative_path,
        gemini_key=gemini_key,
        groq_key=groq_key,
        openrouter_key=openrouter_key,
    )

    # Stage 2: Analyze page
    cleaned_html, page_analysis = await analyze_page(
        url=url, gemini_key=gemini_key, groq_key=groq_key, openrouter_key=openrouter_key,
    )

    # Stage 3: Strategize
    plan = await create_strategy(
        ad_analysis=ad_analysis,
        page_analysis=page_analysis,
        page_html=cleaned_html,
        gemini_key=gemini_key,
        groq_key=groq_key,
        openrouter_key=openrouter_key,
    )

    # Stage 4: Apply (pure Python, no async needed)
    enhanced_html = apply_modifications(cleaned_html, plan)

    # Build report for frontend
    metadata = plan.get("metadata", {})
    modifications = []

    bar = plan.get("announcement_bar") or {}
    if bar.get("enabled"):
        modifications.append(f"Added announcement bar: \"{bar.get('text', '')}\"")

    hero = plan.get("hero_section") or {}
    headline = hero.get("headline") or {}
    if headline.get("replacement"):
        modifications.append(f"Changed headline: \"{headline.get('original', '')}\" → \"{headline['replacement']}\"")
    subheadline = hero.get("subheadline") or {}
    if subheadline.get("replacement"):
        modifications.append(f"Changed subheadline to: \"{subheadline['replacement']}\"")
    cta = hero.get("cta_button") or {}
    if cta.get("new_text"):
        modifications.append(f"Changed CTA: \"{cta.get('original_text', '')}\" → \"{cta['new_text']}\"")

    sp = plan.get("social_proof") or {}
    if sp.get("enabled"):
        modifications.append(f"Added social proof: \"{sp.get('text', '')}\"")

    urg = plan.get("urgency_element") or {}
    if urg.get("enabled"):
        modifications.append(f"Added urgency: \"{urg.get('text', '')}\"")

    for rep in (plan.get("text_replacements") or []):
        orig = rep.get("original_text", "")[:40]
        new = rep.get("new_text", "")[:40]
        modifications.append(f"Replaced text: \"{orig}...\" → \"{new}...\"")

    warnings = plan.get("_validation_warnings", [])

    return {
        "original_html": cleaned_html,
        "enhanced_html": enhanced_html,
        "report": {
            "ad_summary": metadata.get("ad_summary", ""),
            "page_summary": metadata.get("page_summary", ""),
            "alignment_gap": metadata.get("alignment_gap", ""),
            "cro_strategy": metadata.get("cro_strategy", ""),
            "modifications_applied": modifications,
            "validation_warnings": warnings,
        },
        "raw_plan": plan,
    }
