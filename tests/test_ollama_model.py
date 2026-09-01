from habit.baseline import LargeModel, OllamaModel


def test_provider_and_model() -> None:
    assert OllamaModel().provider == "ollama"
    assert OllamaModel().model == "llama3.1:8b"
    assert OllamaModel("qwen2.5:7b").model == "qwen2.5:7b"


def test_satisfies_protocol() -> None:
    model: LargeModel = OllamaModel()
    assert model.provider == "ollama"
