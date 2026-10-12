# Offline model that fails per call with probability 1 - reliability.

import random

from habit.baseline.model import LLMResponse


class ModelFailure(Exception):
    pass


class UnreliableModel:
    def __init__(self, *, reliability: float, seed: int = 0) -> None:
        self._reliability = reliability
        self._rng = random.Random(seed)

    @property
    def provider(self) -> str:
        return "fake-unreliable"

    @property
    def model(self) -> str:
        return "fake-unreliable-1"

    def complete(self, prompt: str) -> LLMResponse:
        if self._rng.random() >= self._reliability:
            raise ModelFailure(
                f"simulated LLM step failure (reliability={self._reliability})"
            )
        return LLMResponse(text="ok", input_tokens=len(prompt.split()), output_tokens=8)
