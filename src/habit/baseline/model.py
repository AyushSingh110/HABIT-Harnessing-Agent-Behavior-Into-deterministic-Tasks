# Large-model interface plus a deterministic offline fake. Groq model arrives in T12.

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int


class LargeModel(Protocol):
    @property
    def provider(self) -> str: ...

    @property
    def model(self) -> str: ...

    def complete(self, prompt: str) -> LLMResponse: ...


class FakeModel:
    @property
    def provider(self) -> str:
        return "fake"

    @property
    def model(self) -> str:
        return "fake-1"

    def complete(self, prompt: str) -> LLMResponse:
        return LLMResponse(text="ok", input_tokens=len(prompt.split()), output_tokens=8)
