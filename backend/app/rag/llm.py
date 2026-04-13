"""
Mistral 7B LLM client via Ollama HTTP API.

Supports both blocking and SSE streaming generation.

Why Ollama?
  - Self-hosted: no data leaves the server (RGPD compliant)
  - Mistral 7B: French company, strong FR language support
  - Simple HTTP API: no gRPC, no custom SDK
  - Docker-native: already in docker-compose.yml
"""
from typing import AsyncGenerator

import httpx

from app.core.config import get_settings

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


def _build_system_prompt(
    context_chunks: list[dict],
    mcp_data: dict | None = None,
    response_lang: str = "fr",
) -> str:
    """Build the full system prompt with retrieved context and MCP data."""
    # Format context chunks
    context_parts = []
    for i, chunk in enumerate(context_chunks, 1):
        source = chunk.get("source", "inconnu")
        chunk_type = chunk.get("type", "inconnu")
        name = chunk.get("name", "")
        text = chunk.get("text", "")
        context_parts.append(f"[{i}] Source: {source} | Type: {chunk_type} | {name}\n{text}")

    context_str = "\n\n".join(context_parts) if context_parts else "Aucune source trouvee."

    # Format MCP data
    mcp_parts = []
    if mcp_data:
        if mcp_data.get("drug"):
            drug = mcp_data["drug"]
            mcp_parts.append(f"Medicament (ANSM): {drug}")
        if mcp_data.get("disease"):
            disease = mcp_data["disease"]
            mcp_parts.append(f"Maladie (ICD-11): {disease}")
    mcp_str = "\n".join(mcp_parts) if mcp_parts else "Aucune donnee temps reel disponible."

    # Language instruction
    lang_instructions = {
        "fr": "Reponds en francais.",
        "ar": "Reponds en arabe standard (MSA).",
        "darija": "Reponds en darija marocain conversationnel. Utilise le contexte medical francais pour formuler une reponse comprehensible en darija.",
    }
    lang_instruction = lang_instructions.get(response_lang, lang_instructions["fr"])

    return MEDICAL_SYSTEM_PROMPT.format(
        language_instruction=lang_instruction,
        context=context_str,
        mcp_context=mcp_str,
    )


async def generate(
    user_message: str,
    context_chunks: list[dict],
    mcp_data: dict | None = None,
    response_lang: str = "fr",
) -> str:
    """
    Generate a complete (non-streaming) response from Mistral 7B.

    Used for testing and fallback when SSE is not needed.
    """
    settings = get_settings()
    ollama_url = f"http://{settings.OLLAMA_HOST}:{settings.OLLAMA_PORT}/api/generate"
    system_prompt = _build_system_prompt(context_chunks, mcp_data, response_lang)

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            ollama_url,
            json={
                "model": settings.OLLAMA_MODEL,
                "system": system_prompt,
                "prompt": user_message,
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "num_predict": 1024,
                    "top_p": 0.9,
                },
            },
        )
        response.raise_for_status()
        return response.json().get("response", "").strip()


async def generate_stream(
    user_message: str,
    context_chunks: list[dict],
    mcp_data: dict | None = None,
    response_lang: str = "fr",
) -> AsyncGenerator[str, None]:
    """
    Stream tokens from Mistral 7B via Ollama.

    Yields individual text tokens as they are generated.
    First token typically arrives in < 200ms.
    """
    settings = get_settings()
    ollama_url = f"http://{settings.OLLAMA_HOST}:{settings.OLLAMA_PORT}/api/generate"
    system_prompt = _build_system_prompt(context_chunks, mcp_data, response_lang)

    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream(
            "POST",
            ollama_url,
            json={
                "model": settings.OLLAMA_MODEL,
                "system": system_prompt,
                "prompt": user_message,
                "stream": True,
                "options": {
                    "temperature": 0.3,
                    "num_predict": 1024,
                    "top_p": 0.9,
                },
            },
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                import json
                data = json.loads(line)
                token = data.get("response", "")
                if token:
                    yield token
                if data.get("done", False):
                    break


async def check_health() -> bool:
    """Check if Ollama is reachable and the model is loaded."""
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"http://{settings.OLLAMA_HOST}:{settings.OLLAMA_PORT}/api/tags"
            )
            resp.raise_for_status()
            models = resp.json().get("models", [])
            return any(m.get("name", "").startswith("mistral") for m in models)
    except Exception:
        return False
