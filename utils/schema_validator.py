import json
import re


ALLOWED_CSS_PROPERTIES = {
    "color", "background-color", "font-size", "font-weight",
    "border", "padding", "border-radius", "opacity",
    "margin-top", "margin-bottom",
}

MAX_TEXT_REPLACEMENTS = 5
MAX_STYLE_MODIFICATIONS = 3
MAX_ELEMENT_VISIBILITY = 2


def validate_modification_plan(plan: dict, page_html: str) -> tuple[bool, list[str]]:
    """Validate a CRO modification plan against constraints.

    Returns (is_valid, list_of_errors).
    If is_valid is False, errors describe what's wrong.
    """
    errors = []

    # Validate metadata
    metadata = plan.get("metadata")
    if not metadata:
        errors.append("Missing 'metadata' section")
    else:
        for field in ("ad_summary", "page_summary", "alignment_gap", "cro_strategy"):
            if not metadata.get(field):
                errors.append(f"Missing metadata.{field}")

    # Validate announcement_bar
    bar = plan.get("announcement_bar")
    if bar and bar.get("enabled"):
        text = bar.get("text", "")
        if len(text) > 80:
            errors.append(f"announcement_bar.text exceeds 80 chars ({len(text)})")
        if not _is_valid_hex(bar.get("background_color", "")):
            errors.append("announcement_bar.background_color is not a valid hex color")
        if not bar.get("reason"):
            errors.append("announcement_bar missing reason")

    # Validate hero_section
    hero = plan.get("hero_section")
    if hero:
        headline = hero.get("headline")
        if headline and headline.get("replacement"):
            if len(headline["replacement"]) > 70:
                errors.append(f"hero headline exceeds 70 chars ({len(headline['replacement'])})")
            if not headline.get("original"):
                errors.append("hero headline missing 'original' text for grounding")
            if not headline.get("reason"):
                errors.append("hero headline missing reason")

        subheadline = hero.get("subheadline")
        if subheadline and subheadline.get("replacement"):
            if len(subheadline["replacement"]) > 140:
                errors.append(f"hero subheadline exceeds 140 chars ({len(subheadline['replacement'])})")
            if not subheadline.get("original"):
                errors.append("hero subheadline missing 'original' text for grounding")

        cta = hero.get("cta_button")
        if cta and cta.get("new_text"):
            if len(cta["new_text"]) > 25:
                errors.append(f"CTA text exceeds 25 chars ({len(cta['new_text'])})")
            if cta.get("new_color") and not _is_valid_hex(cta["new_color"]):
                errors.append("CTA new_color is not a valid hex color")

    # Validate social_proof
    sp = plan.get("social_proof")
    if sp and sp.get("enabled"):
        if not sp.get("text"):
            errors.append("social_proof enabled but no text")
        elif len(sp["text"]) > 100:
            errors.append(f"social_proof text exceeds 100 chars ({len(sp['text'])})")
        if not sp.get("source"):
            errors.append("social_proof missing source attribution")
        if not sp.get("reason"):
            errors.append("social_proof missing reason")

    # Validate urgency_element
    urg = plan.get("urgency_element")
    if urg and urg.get("enabled"):
        if not urg.get("text"):
            errors.append("urgency_element enabled but no text")
        elif len(urg["text"]) > 60:
            errors.append(f"urgency_element text exceeds 60 chars ({len(urg['text'])})")
        if not urg.get("reason"):
            errors.append("urgency_element missing reason")

    # Validate text_replacements
    replacements = plan.get("text_replacements", [])
    if len(replacements) > MAX_TEXT_REPLACEMENTS:
        errors.append(f"Too many text_replacements ({len(replacements)}, max {MAX_TEXT_REPLACEMENTS})")
    for i, rep in enumerate(replacements):
        if not rep.get("original_text"):
            errors.append(f"text_replacements[{i}] missing original_text")
        if not rep.get("new_text"):
            errors.append(f"text_replacements[{i}] missing new_text")
        if rep.get("original_text") and rep.get("new_text"):
            max_len = int(len(rep["original_text"]) * 1.3) + 5
            if len(rep["new_text"]) > max_len:
                errors.append(f"text_replacements[{i}] new_text too long ({len(rep['new_text'])} > {max_len})")
        if not rep.get("reason"):
            errors.append(f"text_replacements[{i}] missing reason")

    # Validate style_modifications
    styles = plan.get("style_modifications", [])
    if len(styles) > MAX_STYLE_MODIFICATIONS:
        errors.append(f"Too many style_modifications ({len(styles)}, max {MAX_STYLE_MODIFICATIONS})")
    for i, style in enumerate(styles):
        prop = style.get("property", "")
        if prop not in ALLOWED_CSS_PROPERTIES:
            errors.append(f"style_modifications[{i}] disallowed property '{prop}'. Allowed: {ALLOWED_CSS_PROPERTIES}")
        if not style.get("reason"):
            errors.append(f"style_modifications[{i}] missing reason")

    # Validate element_visibility
    vis = plan.get("element_visibility", [])
    if len(vis) > MAX_ELEMENT_VISIBILITY:
        errors.append(f"Too many element_visibility ({len(vis)}, max {MAX_ELEMENT_VISIBILITY})")

    return len(errors) == 0, errors


def _is_valid_hex(color: str) -> bool:
    if not color:
        return False
    return bool(re.match(r"^#[0-9a-fA-F]{6}$", color))
