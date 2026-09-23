# AI extension point: connect to the approved Llama inference endpoint.
# Owner: Krish
#
# The raw model call. Takes an already-built context string + question and
# returns Llama's answer. Doesn't know about chunks, retrieval, or attachments
# -- that's orchestrator.py's job, this file only talks to the model.

import os
from dotenv import load_dotenv, find_dotenv

# loads the repo-root .env even when this module is imported from elsewhere
# (e.g. Backend/) -- find_dotenv() walks upward until it finds one
load_dotenv(find_dotenv(usecwd=True))

from openai import OpenAI

CHAT_MODEL = "meta-llama/llama-3.1-8b-instruct"


def _get_inference_client() -> OpenAI:
    """Create the external client only when answer generation is requested."""

    api_key = os.environ.get("INFERENCE_API_KEY")
    if not api_key:
        raise RuntimeError("INFERENCE_API_KEY is required for AI answers")
    return OpenAI(
        base_url=(
            os.environ.get("INFERENCE_API_URL")
            or "https://openrouter.ai/api/v1"
        ),
        api_key=api_key,
    )


def generate_answer(question: str, context: str, model: str = CHAT_MODEL) -> str:
    prompt = f"""Context:
{context}

Question: {question}

Answer the question using only the context above. If the answer isn't in the context, say so."""

    response = _get_inference_client().chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content
