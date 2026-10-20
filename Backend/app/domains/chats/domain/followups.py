"""Helpers that make short follow up questions searchable.

A student who types "put that in bullet points" gives the search nothing to
match against, so the notes it finds are unrelated. These helpers borrow the
topic from the previous question instead. They have no dependencies, so the
chat service and the answer adapters can both use them.
"""

import re

# Longer questions carry their own subject, so they are searched as they are.
FOLLOW_UP_WORD_LIMIT = 15

# Words that point back at an earlier answer or ask for it to be reshaped.
_FOLLOW_UP_CUES = re.compile(
    r"\b(it|its|this|that|these|those|they|them|their|above|previous|"
    r"earlier|last|again|same|more|further|another|also|bullet|bullets|"
    r"points|keywords|table|shorter|shorten|simpler|simplify|briefly|"
    r"example|examples|elaborate|expand|continue|rephrase|summarise|"
    r"summarize|summary)\b",
    re.IGNORECASE,
)

_FOLLOW_UP_OPENERS = (
    "and ",
    "so ",
    "then ",
    "what about",
    "how about",
    "why",
)


def is_follow_up(question: str) -> bool:
    """Return whether the question leans on the earlier conversation."""

    text = question.strip().lower()
    if not text or len(text.split()) > FOLLOW_UP_WORD_LIMIT:
        return False
    if text.startswith(_FOLLOW_UP_OPENERS):
        return True
    return _FOLLOW_UP_CUES.search(text) is not None


def build_retrieval_query(question: str, previous_user_questions: list[str]) -> str:
    """Return the text to search the notes with.

    A standalone question is searched as it is. A follow up is searched
    together with the most recent earlier question, which carries the topic.
    """

    if not previous_user_questions:
        return question
    if not is_follow_up(question):
        return question

    previous = previous_user_questions[-1].strip()
    if not previous:
        return question
    return f"{previous} {question}"
