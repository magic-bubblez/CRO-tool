from __future__ import annotations

import re
from bs4 import BeautifulSoup, NavigableString


def apply_modifications(html: str, plan: dict) -> str:
    """Stage 4: Apply the CRO modification plan to the HTML.

    Pure Python / BeautifulSoup — no LLM calls.
    Applies changes in order: announcement bar, hero, social proof,
    urgency, text replacements, style modifications, element visibility.

    Returns the modified HTML string.
    """
    soup = BeautifulSoup(html, "html.parser")

    _apply_announcement_bar(soup, plan.get("announcement_bar"))
    _apply_hero_changes(soup, plan.get("hero_section"))
    _apply_social_proof(soup, plan.get("social_proof"))
    _apply_urgency(soup, plan.get("urgency_element"))
    _apply_text_replacements(soup, plan.get("text_replacements", []))
    _apply_style_modifications(soup, plan.get("style_modifications", []))
    _apply_element_visibility(soup, plan.get("element_visibility", []))

    return str(soup)


def _apply_announcement_bar(soup: BeautifulSoup, bar: dict | None):
    if not bar or not bar.get("enabled"):
        return

    bg_color = bar.get("background_color", "#FF6B35")
    text_color = bar.get("text_color", "#FFFFFF")
    text = bar.get("text", "")

    bar_html = f'''<div style="
        background-color: {bg_color};
        color: {text_color};
        text-align: center;
        padding: 10px 16px;
        font-size: 14px;
        font-weight: 600;
        letter-spacing: 0.3px;
        position: relative;
        z-index: 9999;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    ">{text}</div>'''

    bar_element = BeautifulSoup(bar_html, "html.parser")

    body = soup.find("body")
    if body:
        body.insert(0, bar_element)


def _apply_hero_changes(soup: BeautifulSoup, hero: dict | None):
    if not hero:
        return

    # Replace headline
    headline = hero.get("headline")
    if headline and headline.get("original") and headline.get("replacement"):
        _find_and_replace_text(soup, headline["original"], headline["replacement"])

    # Replace subheadline
    subheadline = hero.get("subheadline")
    if subheadline and subheadline.get("original") and subheadline.get("replacement"):
        _find_and_replace_text(soup, subheadline["original"], subheadline["replacement"])

    # Replace CTA button text
    cta = hero.get("cta_button")
    if cta and cta.get("original_text") and cta.get("new_text"):
        element = _find_and_replace_text(soup, cta["original_text"], cta["new_text"])
        if element and cta.get("new_color"):
            existing_style = element.get("style", "")
            element["style"] = f"{existing_style}; background-color: {cta['new_color']};"


def _apply_social_proof(soup: BeautifulSoup, sp: dict | None):
    if not sp or not sp.get("enabled"):
        return

    text = sp.get("text", "")
    sp_html = f'''<div style="
        text-align: center;
        padding: 12px 16px;
        font-size: 13px;
        color: #666;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        background-color: #f8f9fa;
        border-top: 1px solid #eee;
        border-bottom: 1px solid #eee;
    ">&#9733; {text}</div>'''

    sp_element = BeautifulSoup(sp_html, "html.parser")
    placement = sp.get("placement", "below_hero")

    _inject_element(soup, sp_element, placement)


def _apply_urgency(soup: BeautifulSoup, urg: dict | None):
    if not urg or not urg.get("enabled"):
        return

    text = urg.get("text", "")
    urg_html = f'''<div style="
        text-align: center;
        padding: 8px 16px;
        font-size: 13px;
        color: #d63031;
        font-weight: 600;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    ">&#9200; {text}</div>'''

    urg_element = BeautifulSoup(urg_html, "html.parser")
    placement = urg.get("placement", "above_cta")

    _inject_element(soup, urg_element, placement)


def _apply_text_replacements(soup: BeautifulSoup, replacements: list):
    for rep in replacements:
        original = rep.get("original_text", "")
        new_text = rep.get("new_text", "")
        if original and new_text:
            _find_and_replace_text(soup, original, new_text)


def _apply_style_modifications(soup: BeautifulSoup, styles: list):
    for style in styles:
        target = style.get("target", "")
        prop = style.get("property", "")
        value = style.get("new_value", "")

        if not (target and prop and value):
            continue

        # Try CSS selector first
        try:
            elements = soup.select(target)
        except Exception:
            elements = []

        # If no match by selector, try finding by text content
        if not elements:
            for tag in soup.find_all(True):
                tag_text = tag.get_text(strip=True)
                if target.lower() in tag_text.lower():
                    elements = [tag]
                    break

        for element in elements:
            existing = element.get("style", "")
            element["style"] = f"{existing}; {prop}: {value};"


def _apply_element_visibility(soup: BeautifulSoup, visibility: list):
    for vis in visibility:
        target = vis.get("target", "")
        method = vis.get("method", "")

        if not (target and method):
            continue

        try:
            elements = soup.select(target)
        except Exception:
            elements = []

        if not elements:
            for tag in soup.find_all(True):
                tag_text = tag.get_text(strip=True)
                if target.lower() in tag_text.lower():
                    elements = [tag]
                    break

        for element in elements:
            existing = element.get("style", "")
            element["style"] = f"{existing}; {method};"


def _find_and_replace_text(soup: BeautifulSoup, original: str, replacement: str):
    """Find text in the HTML and replace it. Returns the parent element if found."""
    # Normalize whitespace for matching
    original_normalized = " ".join(original.split())

    # First try exact match in text nodes
    for text_node in soup.find_all(string=True):
        if not isinstance(text_node, NavigableString):
            continue
        node_normalized = " ".join(text_node.strip().split())
        if original_normalized in node_normalized:
            new_value = text_node.replace(text_node.strip(), replacement)
            text_node.replace_with(new_value)
            return text_node.parent

    # Fallback: try matching against element's full text content
    for tag in soup.find_all(True):
        tag_text = tag.get_text(strip=True)
        tag_text_normalized = " ".join(tag_text.split())
        if original_normalized == tag_text_normalized:
            tag.string = replacement
            return tag

    # Last resort: case-insensitive partial match
    for tag in soup.find_all(True):
        tag_text = tag.get_text(strip=True)
        if original_normalized.lower() in " ".join(tag_text.split()).lower():
            if len(list(tag.children)) <= 1:
                tag.string = replacement
                return tag

    return None


def _inject_element(soup: BeautifulSoup, element, placement: str):
    """Inject an element at the specified placement location."""
    if placement == "below_hero":
        # Find first h1 or large heading, inject after its parent section
        h1 = soup.find("h1")
        if h1:
            # Walk up to find a section-level container
            target = h1.parent
            if target:
                target.insert_after(element)
                return

    if placement == "above_cta":
        # Find first button or link that looks like a CTA
        for tag in soup.find_all(["button", "a"]):
            text = tag.get_text(strip=True).lower()
            if any(kw in text for kw in ("get", "start", "sign", "buy", "order", "try", "claim", "shop", "download")):
                tag.insert_before(element)
                return

    if placement == "below_cta":
        for tag in soup.find_all(["button", "a"]):
            text = tag.get_text(strip=True).lower()
            if any(kw in text for kw in ("get", "start", "sign", "buy", "order", "try", "claim", "shop", "download")):
                tag.insert_after(element)
                return

    # Fallback: inject after body's first child
    body = soup.find("body")
    if body and body.contents:
        body.contents[0].insert_after(element)
