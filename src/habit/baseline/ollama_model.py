# Local Ollama-backed LargeModel. The ollama SDK is imported lazily so offline skips it.

from dataclasses import dataclass

from habit.baseline.model import LLMResponse


@dataclass(frozen=True)
class OllamaModel:
    model: str = "llama3.1:8b"

    @property
    def provider(self) -> str:
        return "ollama"

    def complete(self, prompt: str) -> LLMResponse:
        import ollama

        response = ollama.chat(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
        )
        return LLMResponse(
            text=response["message"]["content"],
            input_tokens=response.get("prompt_eval_count", 0),
            output_tokens=response.get("eval_count", 0),
        )
