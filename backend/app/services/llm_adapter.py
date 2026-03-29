"""
GoatRaw - LLM Adapter Layer
Unified interface across Groq, OpenAI, Together AI.
Routing: fast → Groq | smart → OpenAI | fallback → Together AI
"""

import os
import httpx
import json
import logging
from enum import Enum
from typing import Optional
from app.core.config import settings

logger = logging.getLogger("goatraw.llm")


class ModelType(str, Enum):
    FAST = "fast"       # Groq — low latency, planning/tool-calling
    SMART = "smart"     # OpenAI — complex reasoning, synthesis
    FALLBACK = "fallback"  # Together AI — budget/failover
    LOCAL = "local"     # Ollama — local LLM for privacy/offline


# ─── Provider Configs ─────────────────────────────────────────────────────────

PROVIDER_CONFIG = {
    ModelType.FAST: {
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "model": "llama-3.3-70b-versatile",
        "api_key_env": settings.GROQ_API_KEY,
    },
    ModelType.SMART: {
        "url": "https://api.openai.com/v1/chat/completions",
        "model": "gpt-4o-mini",
        "api_key_env": settings.OPENAI_API_KEY,
    },
    ModelType.FALLBACK: {
        "url": "https://api.together.xyz/v1/chat/completions",
        "model": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "api_key_env": settings.TOGETHER_API_KEY,
    },
    ModelType.LOCAL: {
        "url": os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat"),
        "model": os.getenv("OLLAMA_MODEL", "llama3"),
        "api_key_env": "none",
    },
}


# ─── Core Generate Function ───────────────────────────────────────────────────

async def generate(
    prompt: str,
    model_type: ModelType = ModelType.FAST,
    system_prompt: Optional[str] = None,
    temperature: float = 0.2,
    max_tokens: int = 2048,
    json_mode: bool = False,
) -> str:
    """
    Main LLM generation function.
    Automatically falls back to next provider on failure.
    """
    providers = _get_provider_chain(model_type)

    for provider_key in providers:
        try:
            result = await _call_provider(
                provider_key,
                prompt,
                system_prompt,
                temperature,
                max_tokens,
                json_mode,
            )
            logger.info(f"LLM response via {provider_key}")
            return result
        except Exception as e:
            logger.warning(f"Provider {provider_key} failed: {e}. Trying next...")

    raise RuntimeError("All LLM providers failed.")


def _get_provider_chain(model_type: ModelType) -> list:
    """Returns ordered list of providers to try."""
    if model_type == ModelType.FAST:
        return [ModelType.FAST, ModelType.FALLBACK, ModelType.SMART]
    elif model_type == ModelType.SMART:
        return [ModelType.SMART, ModelType.FAST, ModelType.FALLBACK]
    else:
        return [ModelType.FALLBACK, ModelType.FAST, ModelType.SMART]


async def _call_provider(
    provider_key: ModelType,
    prompt: str,
    system_prompt: Optional[str],
    temperature: float,
    max_tokens: int,
    json_mode: bool,
) -> str:
    config = PROVIDER_CONFIG[provider_key]
    api_key = config["api_key_env"]

    if not api_key and provider_key != ModelType.LOCAL:
        raise ValueError(f"API key not configured for {provider_key}")

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    model_name = config["model"]
    
    # Ollama auto-discovery (if model set to "auto" or empty)
    if provider_key == ModelType.LOCAL:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(config["url"].replace("/api/chat", "/api/tags"))
                if res.status_code == 200:
                    models = res.json().get("models", [])
                    if models:
                        model_name = models[0]["name"]
                        logger.info(f"Ollama: Using discovered model {model_name}")
        except Exception:
            pass

    body = {
        "model": model_name,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    if json_mode and provider_key in [ModelType.SMART]:
        body["response_format"] = {"type": "json_object"}

    # Ollama has a slightly different response structure if using its native /api/chat
    is_ollama = provider_key == ModelType.LOCAL
    if is_ollama:
        body["stream"] = False

    async with httpx.AsyncClient(timeout=120.0) as client:
        headers = {"Content-Type": "application/json"}
        if api_key != "none":
            headers["Authorization"] = f"Bearer {api_key}"
            
        resp = await client.post(config["url"], headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()
        
        if is_ollama:
            return data["message"]["content"]
        return data["choices"][0]["message"]["content"]


# ─── JSON Generation Helper ───────────────────────────────────────────────────

async def generate_json(
    prompt: str,
    model_type: ModelType = ModelType.FAST,
    system_prompt: Optional[str] = None,
) -> dict:
    """Wrapper that forces JSON output and parses it."""
    json_system = (system_prompt or "") + "\nYou MUST respond with valid JSON only. No markdown, no explanation."
    raw = await generate(
        prompt,
        model_type=model_type,
        system_prompt=json_system,
        json_mode=True,
    )
    # Strip markdown fences if present
    clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(clean)
