from __future__ import annotations

import asyncio
import base64
import re
import httpx
from google import genai
from google.genai import types

# Primary: Google AI Studio
GEMINI_MODEL = "gemini-2.5-flash"
PRIMARY_TIMEOUT_FAST = 30   # seconds for vision + text analysis
PRIMARY_TIMEOUT_STRATEGY = 90  # seconds for strategist (large prompt, complex reasoning)

# Fallback chains — different upstreams so they don't fail together
FALLBACK_VISION_CHAIN = [
    "google/gemma-4-31b-it:free",          # Google upstream
    "nvidia/nemotron-nano-12b-v2-vl:free",  # NVIDIA upstream
]
FALLBACK_TEXT_CHAIN = [
    "qwen/qwen3-coder:free",                       # Best for structured JSON output
    "meta-llama/llama-3.3-70b-instruct:free",      # Strong general reasoning
    "nvidia/nemotron-3-super-120b-a12b:free",      # NVIDIA upstream — different provider
    "nousresearch/hermes-3-llama-3.1-405b:free",   # 405B parameter beast
]

TRANSIENT_SIGNALS = ("429", "503", "502", "UNAVAILABLE", "RESOURCE_EXHAUSTED", "overloaded", "Too Many Requests")


def _is_transient(e: Exception) -> bool:
    err = str(e)
    return any(s in err for s in TRANSIENT_SIGNALS)


def _strip_think(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


# ── Gemini primary functions ──

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

    # Retry up to 3 times on empty responses (Gemini sometimes returns None when degraded)
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


# ── OpenRouter fallback — tries a chain of models ──

async def _openrouter_single_call(payload: dict, api_key: str) -> str:
    """Single OpenRouter API call. Returns content or raises."""
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
    """Try each vision model in the chain until one works."""
    with open(image_path, "rb") as f:
        image_bytes = f.read()
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    ext = image_path.rsplit(".", 1)[-1].lower()
    mime_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp", "gif": "image/gif"}
    mime_type = mime_map.get(ext, "image/jpeg")

    last_error = None
    for model in FALLBACK_VISION_CHAIN:
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

    raise ValueError(f"All vision fallback models failed. Last error: {last_error}")


async def _openrouter_chain_text(prompt: str, api_key: str, models: list, max_tokens: int = 4000) -> str:
    """Try each text model in the chain until one works."""
    last_error = None
    for i, model in enumerate(models):
        try:
            if i > 0:
                await asyncio.sleep(3)  # Brief pause between attempts
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

    # Last resort: try Ollama locally
    try:
        print("[Ollama] Trying local model as last resort...")
        result = await _ollama_text(prompt, max_tokens)
        print("[Ollama] Local model succeeded")
        return result
    except Exception as ollama_err:
        print(f"[Ollama] Failed: {str(ollama_err)[:80]}")

    raise ValueError(f"All models failed (cloud + local). Last cloud error: {last_error}")


async def _ollama_text(prompt: str, max_tokens: int = 4000) -> str:
    """Call local Ollama model. No API key needed."""
    async with httpx.AsyncClient(timeout=300) as client:  # local models can be slow
        response = await client.post(
            "http://localhost:11434/api/chat",
            json={
                "model": "gemma3:27b",  # falls back to whatever is available
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"temperature": 0.3, "num_predict": max_tokens},
            },
        )
    if response.status_code != 200:
        raise ValueError(f"Ollama error: {response.status_code}")
    data = response.json()
    content = data.get("message", {}).get("content", "")
    if not content:
        raise ValueError("Ollama returned empty content")
    return _strip_think(content)


# ── Public API with fallback ──

async def call_vision(image_path: str, prompt: str, gemini_key: str, openrouter_key: str = "") -> str:
    """Vision model — Gemini primary, OpenRouter chain fallback."""
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
        if not openrouter_key:
            raise ValueError("Gemini failed and no OpenRouter key configured") from e
        return await _openrouter_chain_vision(image_path, prompt, openrouter_key)


async def call_text(prompt: str, gemini_key: str, openrouter_key: str = "", max_tokens: int = 4000, use_strategist: bool = False) -> str:
    """Text model — Gemini primary, OpenRouter chain fallback."""
    timeout = PRIMARY_TIMEOUT_STRATEGY if use_strategist else PRIMARY_TIMEOUT_FAST
    try:
        result = await asyncio.wait_for(
            _gemini_text(prompt, gemini_key, max_tokens),
            timeout=timeout,
        )
        label = "strategist" if use_strategist else "analyzer"
        print(f"[Primary] Gemini text responded ({label})")
        return result
    except Exception as e:
        if not _is_transient(e) and "empty" not in str(e).lower() and "Timeout" not in type(e).__name__:
            raise
        print(f"[Fallback] Text: Gemini failed ({type(e).__name__}: {str(e)[:80]})")
        if not openrouter_key:
            raise ValueError("Gemini failed and no OpenRouter key configured") from e
        return await _openrouter_chain_text(prompt, openrouter_key, FALLBACK_TEXT_CHAIN, max_tokens)
