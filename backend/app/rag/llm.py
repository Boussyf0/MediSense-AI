"""
LLM client — supports two providers via LLM_PROVIDER env var:

  LLM_PROVIDER=ollama  (default)
    Local Mistral/Llama via Ollama HTTP API.
    • Docker service  : OLLAMA_HOST=ollama (default, CPU-only, ~0.4 tok/s)
    • Native Mac M1   : OLLAMA_HOST=host.docker.internal + `ollama serve` on host
                        → Metal GPU → ~20-40 tok/s

  LLM_PROVIDER=groq
    Groq cloud API — llama-3.1-8b-instant, ~300-500 tok/s, free tier.
    Requires GROQ_API_KEY in .env (console.groq.com).
    Trade-off: data leaves the server (not RGPD-compliant for prod).
"""
import json
import logging
from typing import AsyncGenerator

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

MEDICAL_SYSTEM_PROMPT = """Tu es MediSense, assistant medical IA specialise dans l'aide au triage de symptomes.

REGLES OBLIGATOIRES:
1. Reponds UNIQUEMENT a partir des sources fournies dans le contexte ci-dessous.
2. Si les sources ne contiennent pas l'information demandee, dis exactement:
   "Je ne dispose pas d'informations fiables sur ce sujet. Veuillez consulter votre medecin."
3. Ne JAMAIS inventer de posologie, dosage ou diagnostic.
4. URGENCE — si le patient mentionne: douleur thoracique, difficulte respiratoire,
   perte de conscience, paralysie faciale, douleur intense soudaine -> reponds:
   "URGENCE: Appelez le 15 (SAMU) ou le 141 immediatement."
5. Cite tes sources entre crochets: [Source: nom, type]
6. Termine TOUJOURS par:
   "Ceci est une aide informative et non un diagnostic medical. Consultez un professionnel de sante."

LANGUE: {language_instruction}

CONTEXTE MEDICAL:
{context}

DONNEES TEMPS REEL (MCP):
{mcp_context}"""

_MAX_CONTEXT_CHUNKS = 6
_MAX_CHUNK_TEXT_CHARS = 900
_MAX_MCP_TEXT_CHARS = 600
_NUM_PREDICT = 80  # CPU inference: ~1 tok/s → ~80s; Groq/Metal: < 1s


def _clip(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + " [...]"


def _build_system_prompt(
    context_chunks: list[dict],
    mcp_data: dict | None = None,
    response_lang: str = "fr",
) -> str:
    context_parts = []
    for i, chunk in enumerate(context_chunks[:_MAX_CONTEXT_CHUNKS], 1):
        source = chunk.get("source", "inconnu")
        chunk_type = chunk.get("type", "inconnu")
        name = chunk.get("name", "")
        text = _clip(str(chunk.get("text", "")), _MAX_CHUNK_TEXT_CHARS)
        context_parts.append(f"[{i}] Source: {source} | Type: {chunk_type} | {name}\n{text}")

    context_str = "\n\n".join(context_parts) if context_parts else "Aucune source trouvee."

    mcp_parts = []
    if mcp_data:
        if mcp_data.get("drug"):
            drug = _clip(str(mcp_data["drug"]), _MAX_MCP_TEXT_CHARS)
            mcp_parts.append(f"Medicament (ANSM): {drug}")
        if mcp_data.get("disease"):
            disease = _clip(str(mcp_data["disease"]), _MAX_MCP_TEXT_CHARS)
            mcp_parts.append(f"Maladie (ICD-11): {disease}")
    mcp_str = "\n".join(mcp_parts) if mcp_parts else "Aucune donnee temps reel disponible."

    lang_instructions = {
        "fr": "Reponds en francais.",
        "ar": "Reponds en arabe standard (MSA).",
        "darija": "Reponds en darija marocain conversationnel.",
    }
    lang_instruction = lang_instructions.get(response_lang, lang_instructions["fr"])

    return MEDICAL_SYSTEM_PROMPT.format(
        language_instruction=lang_instruction,
        context=context_str,
        mcp_context=mcp_str,
    )


# ── Ollama backend ────────────────────────────────────────────────────────────

async def _ollama_generate(
    user_message: str,
    system_prompt: str,
) -> str:
    settings = get_settings()
    url = f"http://{settings.OLLAMA_HOST}:{settings.OLLAMA_PORT}/api/generate"
    async with httpx.AsyncClient(timeout=300.0) as client:
        response = await client.post(
            url,
            json={
                "model": settings.OLLAMA_MODEL,
                "system": system_prompt,
                "prompt": user_message,
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "num_predict": _NUM_PREDICT,
                    "top_p": 0.9,
                },
            },
        )
        response.raise_for_status()
        return response.json().get("response", "").strip()


async def _ollama_stream(
    user_message: str,
    system_prompt: str,
) -> AsyncGenerator[str, None]:
    settings = get_settings()
    url = f"http://{settings.OLLAMA_HOST}:{settings.OLLAMA_PORT}/api/generate"
    async with httpx.AsyncClient(timeout=300.0) as client:
        async with client.stream(
            "POST",
            url,
            json={
                "model": settings.OLLAMA_MODEL,
                "system": system_prompt,
                "prompt": user_message,
                "stream": True,
                "options": {
                    "temperature": 0.3,
                    "num_predict": _NUM_PREDICT,
                    "top_p": 0.9,
                },
            },
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                data = json.loads(line)
                token = data.get("response", "")
                if token:
                    yield token
                if data.get("done", False):
                    break


async def _ollama_health() -> bool:
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"http://{settings.OLLAMA_HOST}:{settings.OLLAMA_PORT}/api/tags"
            )
            resp.raise_for_status()
            models = resp.json().get("models", [])
            return len(models) > 0
    except Exception:
        return False


# ── Groq backend ──────────────────────────────────────────────────────────────

async def _groq_generate(
    user_message: str,
    system_prompt: str,
) -> str:
    settings = get_settings()
    url = "https://api.groq.com/openai/v1/chat/completions"
    payload = {
        "model": settings.GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": 0.3,
        "max_tokens": 512,
        "stream": False,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            url,
            json=payload,
            headers={
                "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()


async def _groq_stream(
    user_message: str,
    system_prompt: str,
) -> AsyncGenerator[str, None]:
    settings = get_settings()
    url = "https://api.groq.com/openai/v1/chat/completions"
    payload = {
        "model": settings.GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": 0.3,
        "max_tokens": 512,
        "stream": True,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        async with client.stream(
            "POST",
            url,
            json=payload,
            headers={
                "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue
                chunk = line[6:]  # strip "data: "
                if chunk == "[DONE]":
                    break
                data = json.loads(chunk)
                token = data["choices"][0].get("delta", {}).get("content", "")
                if token:
                    yield token


async def _groq_health() -> bool:
    settings = get_settings()
    if not settings.GROQ_API_KEY:
        return False
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"},
            )
            return resp.status_code == 200
    except Exception:
        return False


# ── Public API ────────────────────────────────────────────────────────────────

async def generate(
    user_message: str,
    context_chunks: list[dict],
    mcp_data: dict | None = None,
    response_lang: str = "fr",
) -> str:
    """Generate a complete response. Provider selected via LLM_PROVIDER setting."""
    settings = get_settings()
    system_prompt = _build_system_prompt(context_chunks, mcp_data, response_lang)
    provider = settings.LLM_PROVIDER.lower()

    if provider == "groq":
        return await _groq_generate(user_message, system_prompt)
    return await _ollama_generate(user_message, system_prompt)


async def generate_stream(
    user_message: str,
    context_chunks: list[dict],
    mcp_data: dict | None = None,
    response_lang: str = "fr",
) -> AsyncGenerator[str, None]:
    """Stream tokens. Provider selected via LLM_PROVIDER setting."""
    settings = get_settings()
    system_prompt = _build_system_prompt(context_chunks, mcp_data, response_lang)
    provider = settings.LLM_PROVIDER.lower()

    if provider == "groq":
        async for token in _groq_stream(user_message, system_prompt):
            yield token
    else:
        async for token in _ollama_stream(user_message, system_prompt):
            yield token


async def check_health() -> bool:
    """Check LLM provider connectivity."""
    settings = get_settings()
    provider = settings.LLM_PROVIDER.lower()
    if provider == "groq":
        return await _groq_health()
    return await _ollama_health()
