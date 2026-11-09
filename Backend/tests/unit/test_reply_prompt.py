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


def test_bullet_and_table_layouts_override_the_sentence_limit() -> None:
    assert "never answer a bullet request with a paragraph" in _system(
        response_format="bullet_points"
    )
    assert "replaces the 2 to 4 sentence guideline" in _system(
        response_format="table"
    )


def test_facilitator_reply_is_cut_down_to_its_guiding_question() -> None:
    reduced = rag_answering._facilitator_question(
        "The paper reports a pass through of 0.4. What do you think drives it?"
    )
    assert reduced == "What do you think drives it?"


def test_facilitator_reply_without_a_question_gets_a_neutral_prompt() -> None:
    reduced = rag_answering._facilitator_question(
        "Exchange rate pass through is high in Turkey."
    )
    assert reduced == rag_answering._FACILITATOR_FALLBACK_QUESTION
    assert "Turkey" not in reduced


def test_source_marker_before_the_final_full_stop_is_removed_and_used() -> None:
    chunks = [object(), object(), object()]
    cleaned, selected = rag_answering._selected_source_chunks(
        "The data covers 260 months [[SOURCE_IDS:2]].",
        chunks,
    )
    assert cleaned == "The data covers 260 months."
    assert selected == [chunks[1]]
    assert "SOURCE_IDS" not in cleaned


def test_source_marker_at_the_end_still_works() -> None:
    chunks = [object(), object()]
    cleaned, selected = rag_answering._selected_source_chunks(
        "A short answer. [[SOURCE_IDS:1,2]]",
        chunks,
    )
    assert cleaned == "A short answer."
    assert selected == [chunks[0], chunks[1]]


def test_quiz_reply_keeps_questions_and_drops_the_printed_answers() -> None:
    reply = (
        "1. Which test rejects parameter stability in 2018M08?\n"
        "The Chow test rejects it.\n"
        "\n"
        "2. What does the CUSUM statistic show?\n"
        "It shows instability.\n"
    )
    cleaned = rag_answering._hide_quiz_answers(reply)
    assert "1. Which test rejects parameter stability in 2018M08?" in cleaned
    assert "2. What does the CUSUM statistic show?" in cleaned
    assert "Chow test rejects" not in cleaned
    assert "instability" not in cleaned


def test_quiz_reply_keeps_an_intro_and_lettered_options() -> None:
    reply = (
        "Here are your questions.\n"
        "1. Which test is used?\n"
        "A) Chow\n"
        "B) Bai Perron\n"
        "Answer: A\n"
    )
    cleaned = rag_answering._hide_quiz_answers(reply)
    assert cleaned.startswith("Here are your questions.")
    assert "A) Chow" in cleaned
    assert "B) Bai Perron" in cleaned
    assert "Answer: A" not in cleaned


def test_quiz_answers_are_kept_when_the_student_asks_for_them() -> None:
    assert rag_answering._asks_for_answers("Quiz me and give the answers too")
    assert not rag_answering._asks_for_answers("Quiz me on structural breaks")


def test_a_partly_covered_question_gets_the_covered_part_and_names_the_gap() -> None:
    system = _system()
    assert "If the notes cover only part of the question" in system
    assert "never fill the missing part from general knowledge" in system


@pytest.mark.asyncio
async def test_a_refusal_ends_with_the_upload_tip_once(monkeypatch) -> None:
    monkeypatch.setattr(
        rag_answering,
        "generate_answer",
        lambda question, context, *, response_format=None, mode=None: (
            "The answer is not available in the supplied study material."
        ),
    )
    generator = rag_answering.KrishRagAnswerGenerator(top_k=5, rank_chunks=False)
    answer = await generator.answer_question(question="Q", chunks=(_chunk(),))
    assert answer.content.endswith(rag_answering._UPLOAD_TIP)
    assert answer.content.count("Tip:") == 1
    assert answer.sources == ()


@pytest.mark.asyncio
async def test_a_grounded_answer_gets_no_upload_tip(monkeypatch) -> None:
    monkeypatch.setattr(
        rag_answering,
        "generate_answer",
        lambda question, context, *, response_format=None, mode=None: (
            "The base model uses 8 attention heads. [[SOURCE_IDS:1]]"
        ),
    )
    generator = rag_answering.KrishRagAnswerGenerator(top_k=5, rank_chunks=False)
    answer = await generator.answer_question(question="Q", chunks=(_chunk(),))
    assert "Tip:" not in answer.content
    assert len(answer.sources) == 1
