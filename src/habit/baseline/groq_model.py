# Real Groq-backed LargeModel. The groq SDK is imported lazily so offline paths skip it.

from dataclasses import dataclass

from habit.baseline.model import LLMResponse


@dataclass(frozen=True)
class GroqModel:
    model: str = "llama-3.3-70b-versatile"

    @property
    def provider(self) -> str:
        return "groq"

    def complete(self, prompt: str) -> LLMResponse:
        from groq import Groq

        client = Groq()
        response = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
        )
        usage = response.usage
        if usage is None:
            raise RuntimeError("Groq response has no usage data")
        return LLMResponse(
            text=response.choices[0].message.content or "",
            input_tokens=usage.prompt_tokens,
            output_tokens=usage.completion_tokens,
        )
