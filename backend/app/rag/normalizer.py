"""
Query normalizer — translates Darija/AR to clinical French before retrieval.

Why translate before retrieval?
  Embedding Darija directly against a French corpus yields poor similarity scores.
  "rasi kaydrni" and "cephalees" are semantically identical but live in different
  embedding sub-spaces even in multilingual models. Translating to French first
  ensures the query and corpus share the same linguistic space.

The original language is preserved so the LLM can respond in the patient's language.
"""
import httpx

from app.core.config import get_settings

_TRANSLATE_PROMPT = """Tu es un traducteur medical. Traduis le message patient suivant en francais medical clinique.
Regles:
- Utilise la terminologie medicale appropriee
- Preserve tous les symptomes, medicaments et durees mentionnes
- Ne rajoute AUCUNE information
- Retourne UNIQUEMENT la traduction, sans explication

Message patient: {message}

Traduction en francais medical:"""


async def normalize_to_french(text: str, source_lang: str) -> str:
    """
    Translate AR/Darija text to clinical French via Mistral 7B.

    If source_lang is already 'fr', returns the text unchanged.
    """
    if source_lang == "fr":
        return text

    settings = get_settings()
    ollama_url = f"http://{settings.OLLAMA_HOST}:{settings.OLLAMA_PORT}/api/generate"

    prompt = _TRANSLATE_PROMPT.format(message=text)

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            ollama_url,
            json={
                "model": settings.OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,  # low temp for faithful translation
                    "num_predict": 256,
                },
            },
        )
        response.raise_for_status()
        data = response.json()
        return data.get("response", text).strip()
