"""Recognise messages that are only social chat, such as "okay thanks".

The study assistant answers questions from the student's own material. A
message like "okay thanks" is not a question. Searching the notes for it gave
a confusing "not available in the supplied study material" reply and a list of
irrelevant sources. This module spots such messages so they can get a short,
friendly reply instead.

The match is deliberately strict: the WHOLE message must be made of social
phrases, so "thanks, can you explain entropy?" is still a real question and is
answered from the material as usual.

The replies are fixed text and never repeat the student's words, so there is
nothing here for a prompt injection to take over.
"""

import re

# Order matters: the first pattern that matches the start of the text wins, and
# inside one pattern longer phrases come first ("thank you" before "thank"),
# because the regular expression does not go back to try a longer one.
_PATTERNS = (
    (
        "thanks",
        r"thank you|thank u|thankyou|many thanks|thanks|thank|thx|thnx|tysm|ty|"
        r"cheers|much appreciated|appreciate it",
    ),
    (
        "greeting",
        r"good morning|good afternoon|good evening|good day|hello|hi+|hey+|"
        r"hii+|yo|hola|howdy|sup",
    ),
    (
        "how_are_you",
        r"how are you(?: doing| today| going)?|how r u|how are things|"
        r"how is it going|how's it going|hows it going|what's up|whats up|wassup",
    ),
    (
        "about",
        r"who are you|what are you|what can you do|what do you do|"
        r"how can you help(?: me)?|can you help(?: me)?|help me|help",
    ),
    (
        "farewell",
        r"goodbye|good bye|bye(?: bye)?|see you(?: later| soon| tomorrow)?|"
        r"see ya|cya|good night|goodnight|take care|talk later|ttyl",
    ),
    (
        "acknowledgement",
        r"ok(?:ay)?|okey|kk?|alright|all right|cool|nice|great|awesome|perfect|"
        r"got it|gotcha|understood|i see|makes sense|sounds good|noted|fine|"
        r"good|sure|hmm+|oh+|ah+|wow|lol|haha+|that is all|thats all|"
        r"that will do|nothing else|no more questions",
    ),
)

# Harmless extra words that may follow a social phrase ("thanks a lot",
# "thanks for the help"). They never make a message social on their own.
_FILLERS = (
    r"there|everyone|all|team|companion|assistant|bot|buddy|mate|bro|man|"
    r"a lot|so much|very much|again|then|now|"
    r"for (?:that|now|your help|the help|the answer|the answers|the summary|everything)"
)

# When several kinds appear ("okay thanks bye") the reply follows this order.
_PRIORITY = ("thanks", "farewell", "greeting", "how_are_you", "about", "acknowledgement")

_MAX_LENGTH = 60

_REPLIES = {
    "thanks": "You're welcome! Let me know if you would like to go through anything else in your notes.",
    "greeting": "Hi! I'm your study companion. Ask me a question about your notes or uploaded files whenever you're ready.",
    "how_are_you": "I'm doing well, thank you for asking! What would you like to look at in your notes today?",
    "about": (
        "I'm Smart Peer Companion, an AI study assistant. I answer questions using only "
        "your own notes and files, and I can summarise them, quiz you, or help you think "
        "through a topic. What would you like to do?"
    ),
    "farewell": "Goodbye! Good luck with your studying.",
    "acknowledgement": "Got it. Ask me another question about your notes any time.",
}


def _normalise(text: str) -> str:
    """Lowercase, drop punctuation, digits and emoji, and collapse spaces."""

    text = text.lower().replace("\u2019", "'")
    text = re.sub(r"[^a-z' ]+", " ", text)
    return " ".join(text.split())


def detect_small_talk(question: str) -> str | None:
    """Return the kind of small talk, or None when this is a real question."""

    text = _normalise(question)
    if not text or len(text) > _MAX_LENGTH:
        return None

    found: list[str] = []
    while text:
        for kind, pattern in _PATTERNS:
            match = re.match(rf"(?:{pattern})(?:\s+|$)", text)
            if match:
                found.append(kind)
                text = text[match.end():]
                break
        else:
            filler = re.match(rf"(?:{_FILLERS})(?:\s+|$)", text)
            if filler and found:
                text = text[filler.end():]
            else:
                return None

    for kind in _PRIORITY:
        if kind in found:
            return kind
    return None


def small_talk_reply(kind: str) -> str:
    """The fixed reply for one kind of small talk."""

    return _REPLIES[kind]


def answer_small_talk(question: str) -> str | None:
    """A friendly reply when the message is only social chat, otherwise None."""

    kind = detect_small_talk(question)
    if kind is None:
        return None
    return small_talk_reply(kind)
