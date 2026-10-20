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
from app.domains.chats.application.prompt_security import (
    build_secure_chat_messages,
)

_client = OpenAI(
    base_url=os.environ.get("INFERENCE_API_URL") or "https://openrouter.ai/api/v1",
    api_key=os.environ.get("INFERENCE_API_KEY"),
)
DEFAULT_CHAT_MODEL = "meta-llama/llama-3.1-8b-instruct"

# Set CHAT_MODEL in the environment to try another model without a code
# change. An empty value falls back to the default.
CHAT_MODEL = os.environ.get("CHAT_MODEL") or DEFAULT_CHAT_MODEL


def generate_answer(
    question: str,
    context: str,
    model: str = CHAT_MODEL,
    response_format: str | None = None,
    mode: str | None = None,
    history: list[dict[str, str]] | None = None,
) -> str:
    """Generate a grounded answer, optionally in a requested display format
    and AI mode (default/summarizer/quiz/facilitator).

    Format and mode are passed straight through to build_secure_chat_messages,
    which decides how they're safely woven into the TRUSTED system message --
    never into the untrusted study_context or student_question payload.
    history (earlier turns of the same chat) goes to the same function, which
    treats it as untrusted data next to the study context.
    """

    messages = build_secure_chat_messages(
        question=question,
        context=context,
        response_format=response_format,
        mode=mode,
        history=history,
    )

    response = _client.chat.completions.create(
        model=model,
        messages=messages,
    )
    return response.choices[0].message.content
