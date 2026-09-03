# Interface for the externally hosted trained model, independent of any provider SDK.
# TODO (backend): implement timeouts, bounded retries and provider credential handling.
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True, slots=True)
class InferenceRequest:
    prompt: str
    context: tuple[str, ...] = field(default_factory=tuple)
    model: str | None = None
    max_tokens: int = 1024
    temperature: float = 0.2


@dataclass(frozen=True, slots=True)
class InferenceResponse:
    text: str
    model: str
    provider_request_id: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None


class InferenceProvider(Protocol):
    async def generate(self, request: InferenceRequest) -> InferenceResponse:
        """Generate a response without leaking provider SDK types upstream."""
