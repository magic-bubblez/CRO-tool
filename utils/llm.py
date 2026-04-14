from __future__ import annotations

import asyncio
import base64
import re
import httpx
from google import genai
from google.genai import types

# Primary: Google AI Studio
GEMINI_MODEL = "gemini-2.5-flash"
PRIMARY_TIMEOUT_FAST = 30
PRIMARY_TIMEOUT_STRATEGY = 90

# Groq models (free tier: 30 req/min, 14,400 req/day)
GROQ_VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
GROQ_TEXT_MODEL = "llama-3.3-70b-versatile"
GROQ_STRATEGIST_MODEL = "llama-3.3-70b-versatile"

# OpenRouter free models (last resort)
OPENROUTER_VISION_CHAIN = [
    "google/gemma-4-31b-it:free",
    "nvidia/nemotron-nano-12b-v2-vl:free",
]
OPENROUTER_TEXT_CHAIN = [
    "qwen/qwen3-coder:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "nousresearch/hermes-3-llama-3.1-405b:free",
]

TRANSIENT_SIGNALS = ("429", "503", "502", "UNAVAILABLE", "RESOURCE_EXHAUSTED", "overloaded", "Too Many Requests")


def _is_transient(e: Exception) -> bool:
    err = str(e)
    return any(s in err for s in TRANSIENT_SIGNALS)


def _strip_think(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


# ── Gemini (primary) ──

def _gemini_client(api_key: str):
    return genai.Client(api_key=api_key)


async def _gemini_vision(image_path: str, prompt: str, api_key: str) -> str:
    client = _gemini_client(api_key)

    with open(image_path, "rb") as f:
        image_bytes = f.read()

    ext = image_path.rsplit(".", 1)[-1].lower()
    mime_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp", "gif": "image/gif"}
    mime_type = mime_map.get(ext, "image/jpeg")

    image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
    text_part = types.Part.from_text(text=prompt)

    for attempt in range(3):
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=GEMINI_MODEL,
            contents=[image_part, text_part],
            config=types.GenerateContentConfig(temperature=0.2, max_output_tokens=2000),
        )
        result = response.text or ""
        if result.strip():
            return _strip_think(result)
        print(f"[Gemini] Vision empty response, retry {attempt+1}/3")
        await asyncio.sleep(2)

    raise ValueError("Gemini returned empty response after 3 retries")


async def _gemini_text(prompt: str, api_key: str, max_tokens: int = 4000) -> str:
    client = _gemini_client(api_key)

    for attempt in range(3):
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.3, max_output_tokens=max_tokens),
        )
        result = response.text or ""
        if result.strip():
            return _strip_think(result)
        print(f"[Gemini] Text empty response, retry {attempt+1}/3")
        await asyncio.sleep(2)

    raise ValueError("Gemini returned empty response after 3 retries")


# ── Groq (first fallback — fast, generous limits) ──

async def _groq_call(payload: dict, api_key: str) -> str:
    """Single Groq API call."""
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )

    if response.status_code >= 400:
        raise ValueError(f"Groq {response.status_code}: {response.text[:200]}")

    data = response.json()
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    if not content:
        raise ValueError(f"Groq returned empty content")
    return _strip_think(content)


async def _groq_vision(image_path: str, prompt: str, api_key: str) -> str:
    with open(image_path, "rb") as f:
        image_bytes = f.read()
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    ext = image_path.rsplit(".", 1)[-1].lower()
    mime_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp", "gif": "image/gif"}
    mime_type = mime_map.get(ext, "image/jpeg")

    payload = {
        "model": GROQ_VISION_MODEL,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_b64}"}},
            ],
        }],
        "max_tokens": 2000,
        "temperature": 0.2,
    }
    return await _groq_call(payload, api_key)


async def _groq_text(prompt: str, api_key: str, max_tokens: int = 4000, use_strategist: bool = False) -> str:
    model = GROQ_STRATEGIST_MODEL if use_strategist else GROQ_TEXT_MODEL
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.3,
    }
    return await _groq_call(payload, api_key)


# ── OpenRouter (last resort) ──

async def _openrouter_single_call(payload: dict, api_key: str) -> str:
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )

    if response.status_code == 429:
        raise ValueError(f"429 rate limited: {response.text[:200]}")
    if response.status_code >= 400:
        raise ValueError(f"{response.status_code}: {response.text[:200]}")

    data = response.json()
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    if not content:
        raise ValueError(f"Empty content from OpenRouter: {str(data)[:200]}")
    return _strip_think(content)


async def _openrouter_chain_vision(image_path: str, prompt: str, api_key: str) -> str:
    with open(image_path, "rb") as f:
        image_bytes = f.read()
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    ext = image_path.rsplit(".", 1)[-1].lower()
    mime_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp", "gif": "image/gif"}
    mime_type = mime_map.get(ext, "image/jpeg")

    last_error = None
    for model in OPENROUTER_VISION_CHAIN:
        try:
            print(f"[OpenRouter] Trying vision model: {model}")
            payload = {
                "model": model,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_b64}"}},
                    ],
                }],
                "max_tokens": 2000,
                "temperature": 0.2,
            }
            result = await _openrouter_single_call(payload, api_key)
            print(f"[OpenRouter] Vision succeeded with: {model}")
            return result
        except Exception as e:
            print(f"[OpenRouter] {model} failed: {str(e)[:80]}")
            last_error = e
            continue

    raise ValueError(f"All OpenRouter vision models failed. Last error: {last_error}")


async def _openrouter_chain_text(prompt: str, api_key: str, max_tokens: int = 4000) -> str:
    last_error = None
    for i, model in enumerate(OPENROUTER_TEXT_CHAIN):
        try:
            if i > 0:
                await asyncio.sleep(3)
            print(f"[OpenRouter] Trying text model: {model}")
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": 0.3,
            }
            result = await _openrouter_single_call(payload, api_key)
            print(f"[OpenRouter] Text succeeded with: {model}")
            return result
        except Exception as e:
            print(f"[OpenRouter] {model} failed: {str(e)[:80]}")
            last_error = e
            continue

    raise ValueError(f"All OpenRouter text models failed. Last error: {last_error}")


# ── Public API: Gemini → Groq → OpenRouter ──

async def call_vision(image_path: str, prompt: str, gemini_key: str, groq_key: str = "", openrouter_key: str = "") -> str:
    """Vision: Gemini → Groq → OpenRouter chain."""
    # Try Gemini
    try:
        result = await asyncio.wait_for(
            _gemini_vision(image_path, prompt, gemini_key),
            timeout=PRIMARY_TIMEOUT_FAST,
        )
        print("[Primary] Gemini vision responded")
        return result
    except Exception as e:
        if not _is_transient(e) and "empty" not in str(e).lower() and "Timeout" not in type(e).__name__:
            raise
        print(f"[Fallback] Vision: Gemini failed ({type(e).__name__}: {str(e)[:80]})")

    # Try Groq
    if groq_key:
        try:
            result = await _groq_vision(image_path, prompt, groq_key)
            print("[Groq] Vision succeeded")
            return result
        except Exception as e:
            print(f"[Groq] Vision failed: {str(e)[:80]}")

    # Try OpenRouter
    if openrouter_key:
        return await _openrouter_chain_vision(image_path, prompt, openrouter_key)

    raise ValueError("All vision providers failed")


async def call_text(prompt: str, gemini_key: str, groq_key: str = "", openrouter_key: str = "", max_tokens: int = 4000, use_strategist: bool = False) -> str:
    """Text: Gemini → Groq → OpenRouter chain."""
    label = "strategist" if use_strategist else "analyzer"
    timeout = PRIMARY_TIMEOUT_STRATEGY if use_strategist else PRIMARY_TIMEOUT_FAST

    # Try Gemini
    try:
        result = await asyncio.wait_for(
            _gemini_text(prompt, gemini_key, max_tokens),
            timeout=timeout,
        )
        print(f"[Primary] Gemini text responded ({label})")
        return result
    except Exception as e:
        if not _is_transient(e) and "empty" not in str(e).lower() and "Timeout" not in type(e).__name__:
            raise
        print(f"[Fallback] Text ({label}): Gemini failed ({type(e).__name__}: {str(e)[:80]})")

    # Try Groq
    if groq_key:
        try:
            result = await _groq_text(prompt, groq_key, max_tokens, use_strategist)
            print(f"[Groq] Text succeeded ({label})")
            return result
        except Exception as e:
            print(f"[Groq] Text failed ({label}): {str(e)[:80]}")

    # Try OpenRouter
    if openrouter_key:
        return await _openrouter_chain_text(prompt, openrouter_key, max_tokens)

    raise ValueError(f"All text providers failed ({label})")
