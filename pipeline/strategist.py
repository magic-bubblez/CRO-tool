import json
import re
from utils.prompts import STRATEGIST_PROMPT
from utils.schema_validator import validate_modification_plan
from utils.llm import call_text


async def create_strategy(
    ad_analysis: str,
    page_analysis: str,
    page_html: str,
    gemini_key: str = "",
    openrouter_key: str = "",
    max_retries: int = 2,
) -> dict:
    """Stage 3: Generate a CRO modification plan."""
    prompt = STRATEGIST_PROMPT.format(
        ad_analysis=ad_analysis,
        page_analysis=page_analysis,
    )

    for attempt in range(max_retries):
        raw_output = await call_text(prompt, gemini_key, openrouter_key, max_tokens=8000, use_strategist=True)

        if not raw_output:
            if attempt < max_retries - 1:
                continue
            raise ValueError("Empty strategy response")

        # Parse JSON — handle markdown code fences
        json_str = raw_output.strip()
        if json_str.startswith("```"):
            lines = json_str.split("\n")
            end = len(lines) - 1
            for i in range(len(lines) - 1, 0, -1):
                if lines[i].strip().startswith("```"):
                    end = i
                    break
            json_str = "\n".join(lines[1:end])

        try:
            plan = json.loads(json_str)
        except json.JSONDecodeError as e:
            if attempt < max_retries - 1:
                prompt += f"\n\nYour previous response was not valid JSON. Error: {e}. Please respond with ONLY a valid JSON object, no markdown fences, no explanation."
                continue
            raise ValueError(f"Failed to parse LLM output as JSON after {max_retries} attempts: {e}")

        is_valid, errors = validate_modification_plan(plan, page_html)

        if is_valid:
            return plan

        if attempt < max_retries - 1:
            error_msg = "\n".join(f"- {e}" for e in errors)
            prompt += f"\n\nYour previous output had validation errors:\n{error_msg}\nPlease fix these issues and respond with ONLY a valid JSON object."
            continue

        plan["_validation_warnings"] = errors
        return plan

    raise ValueError("Strategy generation failed after all retries")
