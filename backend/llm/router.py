import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import asyncio
import json
import re
import logging
import requests
import httpx
from groq import AsyncGroq, RateLimitError as GroqRateLimit
from config import GROQ_API_KEY, GROQ_MODEL

logger = logging.getLogger("cliniq")

# Read optional provider keys (graceful if absent)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

_groq_client: AsyncGroq | None = None


def _groq() -> AsyncGroq:
    global _groq_client
    if _groq_client is None:
        _groq_client = AsyncGroq(api_key=GROQ_API_KEY)
    return _groq_client


async def _try_groq(prompt: str, temperature: float, max_tokens: int) -> str:
    response = await _groq().chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content.strip()


async def _try_gemini(prompt: str, temperature: float, max_tokens: int) -> str:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY not set")

    import google.generativeai as genai
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(
        "gemini-1.5-flash",
        generation_config=genai.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        ),
    )
    # Gemini SDK is sync — run in thread pool to stay non-blocking
    response = await asyncio.to_thread(model.generate_content, prompt)
    return response.text.strip()


async def _try_openrouter(prompt: str, temperature: float, max_tokens: int) -> str:
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY not set")

    payload = {
        "model": "mistralai/mistral-7b-instruct",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://cliniq.app",
    }

    def _call():
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=30,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()

    return await asyncio.to_thread(_call)


async def complete(
    prompt: str,
    temperature: float = 0.3,
    max_tokens: int = 1000,
) -> tuple[str, str]:
    """
    Attempt LLM completion with automatic provider fallback.

    Returns (response_text, provider_used).
    Raises RuntimeError if all providers fail.
    """
    providers = [
        ("groq", _try_groq),
        ("gemini", _try_gemini),
        ("openrouter", _try_openrouter),
    ]

    last_error: Exception | None = None
    for name, fn in providers:
        try:
            text = await fn(prompt, temperature, max_tokens)
            logger.info(json.dumps({"stage": "llm.provider_used", "provider": name}))
            return text, name
        except GroqRateLimit as e:
            logger.warning(json.dumps({"stage": "llm.rate_limit", "provider": name, "error": str(e)}))
            last_error = e
        except Exception as e:
            logger.warning(json.dumps({"stage": "llm.provider_error", "provider": name, "error": str(e)}))
            last_error = e

    raise RuntimeError(f"All LLM providers failed. Last error: {last_error}")


async def llm_chat(
    messages: list,
    temperature: float = 0.3,
    max_tokens: int = 2048,
) -> str:
    """
    Send a messages-list completion request.
    Tries Groq first; falls back to OpenRouter on any failure.
    Returns the response content string. Raises if both fail.
    """
    try:
        response = await _groq().chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        logger.warning("Groq failed (%s): %s", type(e).__name__, e)

    if not OPENROUTER_API_KEY:
        raise RuntimeError("Groq failed and OPENROUTER_API_KEY not set")

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                OPENROUTER_URL,
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://cliniq.app",
                    "X-Title": "ClinIQ",
                },
                json={
                    "model": OPENROUTER_MODEL,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"] or ""
    except Exception as e:
        logger.error("OpenRouter failed (%s): %s", type(e).__name__, e)
        raise


def parse_json(text: str) -> dict:
    """Shared JSON extractor used by agents that call complete()."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        return json.loads(match.group())
    raise ValueError("No valid JSON found in LLM response")
