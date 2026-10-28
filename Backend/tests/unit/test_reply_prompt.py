"""Tests for the reply prompt rules and for hiding sources on a refusal."""

import pytest

from app.domains.chats.application.prompt_security import build_secure_chat_messages
from app.domains.chats.domain.models import ChatSource
from app.domains.chats.domain.retrieval import GroundingChunk
from app.domains.chats.infrastructure import rag_answering


def _system(mode=None, response_format=None):
    messages = build_secure_chat_messages(
        question="What does the paper say?",
        context="Some study material.",
        response_format=response_format,
        mode=mode,
    )
    return messages[0]["content"]


def test_a_normal_answer_is_kept_short() -> None:
    system = _system()
    assert "2 to 4 sentences" in system
    assert "Do not add general background" in system


def test_the_notes_are_the_only_source_even_for_well_known_facts() -> None:
    system = _system()
    assert "Stay inside the notes" in system
    assert "sports results" in system
    # the exact phrase the adapter looks for must still be present
    assert "not available in the supplied study material" in system


def test_the_mode_instruction_comes_last() -> None:
    for mode, opening in (
        ("facilitator", "You are acting as Facilitator"),
        ("quiz", "You are acting as QuizMaster"),
        ("summarizer", "You are acting as Summarizer"),
    ):
        system = _system(mode=mode, response_format="paragraph")
        assert system.index(opening) > system.index("Respond in flowing paragraph")


def test_quiz_and_facilitator_skip_the_default_paragraph_layout() -> None:
    for mode in ("quiz", "facilitator"):
        system = _system(mode=mode, response_format=None)
        assert "No layout was chosen in the app" not in system
    default_system = _system(mode="default", response_format=None)
    assert "No layout was chosen in the app" in default_system


def test_a_picker_choice_still_applies_in_every_mode() -> None:
    for mode in ("default", "summarizer", "quiz", "facilitator"):
        system = _system(mode=mode, response_format="bullet_points")
        assert "at most 7 bullets" in system


def test_quiz_never_prints_answers_and_facilitator_never_states_facts() -> None:
    assert "Never write an 'Answer:' line" in _system(mode="quiz")
    facilitator = _system(mode="facilitator")
    assert "Never include a number, a name or a finding" in facilitator


def _chunk() -> GroundingChunk:
    source = ChatSource(note_id=1, note_title="Paper", chunk_id=1, page=1)
    return GroundingChunk(content="Notes text", source=source)


@pytest.mark.parametrize(
    "reply",
    [
        "The answer is not available in the supplied study material.",
        "The study material does not mention Bitcoin regulation in Turkey.",
        "The authors did not choose it, as it is not mentioned in your notes. "
        "The discussion is about Random Forest instead.",
        "Bayesian models are not covered in your notes.",
    ],
)
@pytest.mark.asyncio
async def test_short_replies_that_say_the_notes_do_not_cover_it_show_no_sources(
    monkeypatch, reply
) -> None:
    monkeypatch.setattr(
        rag_answering,
        "generate_answer",
        lambda question, context, *, response_format=None, mode=None: reply,
    )
    generator = rag_answering.KrishRagAnswerGenerator(top_k=5, rank_chunks=False)
    answer = await generator.answer_question(question="Q", chunks=(_chunk(),))
    assert answer.sources == ()


@pytest.mark.asyncio
async def test_a_partial_answer_keeps_its_sources(monkeypatch) -> None:
    reply = (
        "The data covers June 2003 to January 2025 with 260 monthly "
        "observations across eight indicators. The price level is the target "
        "and the other seven are predictors. The notes do not mention the "
        "exact database name."
    )
    monkeypatch.setattr(
        rag_answering,
        "generate_answer",
        lambda question, context, *, response_format=None, mode=None: reply,
    )
    generator = rag_answering.KrishRagAnswerGenerator(top_k=5, rank_chunks=False)
    answer = await generator.answer_question(question="Q", chunks=(_chunk(),))
    assert len(answer.sources) == 1


@pytest.mark.asyncio
async def test_a_long_reply_is_never_treated_as_a_refusal(monkeypatch) -> None:
    reply = "It does not mention anything odd. " + ("Detail. " * 100)
    monkeypatch.setattr(
        rag_answering,
        "generate_answer",
        lambda question, context, *, response_format=None, mode=None: reply,
    )
    generator = rag_answering.KrishRagAnswerGenerator(top_k=5, rank_chunks=False)
    answer = await generator.answer_question(question="Q", chunks=(_chunk(),))
    assert len(answer.sources) == 1


@pytest.mark.asyncio
async def test_a_facilitator_hint_shows_no_sources(monkeypatch) -> None:
    monkeypatch.setattr(
        rag_answering,
        "generate_answer",
        lambda question, context, *, response_format=None, mode=None: (
            "What do you notice about how the two series move together?"
        ),
    )
    generator = rag_answering.KrishRagAnswerGenerator(top_k=5, rank_chunks=False)
    answer = await generator.answer_question(
        question="Q", chunks=(_chunk(),), mode="facilitator"
    )
    assert answer.sources == ()
