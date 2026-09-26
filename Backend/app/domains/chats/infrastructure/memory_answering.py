"""Deterministic lexical answer adapter used before Krish's RAG merge."""

import re

from app.domains.chats.domain.answering import (
    ChatAnswerGenerator,
    GeneratedAnswer,
)
from app.domains.chats.domain.retrieval import GroundingChunk


class LocalGroundedAnswerGenerator(ChatAnswerGenerator):
    """Select a relevant local chunk without pretending to be an AI model."""

    async def answer_question(
        self,
        *,
        question: str,
        chunks: tuple[GroundingChunk, ...],
        response_format: str | None = None,
    ) -> GeneratedAnswer:
        """Choose the chunk sharing the most useful words with the question.

        response_format is accepted to match the updated ChatAnswerGenerator
        interface but ignored here -- this is a deterministic demo fallback,
        not a real model call, so there's no formatting to apply.
        """

        question_terms = _meaningful_terms(question)
        selected = max(
            chunks,
            key=lambda chunk: len(
                question_terms.intersection(_meaningful_terms(chunk.content))
            ),
        )
        return GeneratedAnswer(
            content=(
                "Temporary local demo answer based on "
                f"{selected.source.note_title}: {selected.content}"
            ),
            sources=(selected.source,),
        )


def _meaningful_terms(value: str) -> set[str]:
    """Return normalized words suitable for a tiny deterministic ranking."""

    stop_words = {
        "about",
        "and",
        "are",
        "does",
        "explain",
        "for",
        "from",
        "how",
        "the",
        "this",
        "what",
        "with",
    }
    return {
        term
        for term in re.findall(r"[a-z0-9]+", value.lower())
        if len(term) > 2 and term not in stop_words
    }
