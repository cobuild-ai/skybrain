import pytest
from skybrain.review.lenses.resilience import ResilienceLens
from skybrain.review.models import Category, Severity


class DummyClient:
    def __init__(self, response_text: str):
        self.response_text = response_text

    def query(self, messages, temperature=0.1, max_tokens=2048):
        return self.response_text


def test_resilience_lens_metadata():
    lens = ResilienceLens(client=DummyClient("[]"))
    assert lens.name == "Resilience"
    assert lens.category == Category.RESILIENCE
    assert "Decoupled Lifecycle Guard" in lens.system_prompt
    assert "Immediate Invalidation" in lens.system_prompt
    assert "Transparent Self-Healing" in lens.system_prompt


def test_resilience_lens_parses_findings():
    fake_json = """
    ```json
    [
      {
        "line": 45,
        "severity": "CRITICAL",
        "principle_violated": "Decoupled Lifecycle: Persistent zombie binder handle",
        "description": "SpeechRecognizer instance kept indefinitely without disconnection detection.",
        "suggestion": "Destroy and re-instantiate SpeechRecognizer cleanly per session."
      },
      {
        "line": 88,
        "severity": "HIGH",
        "principle_violated": "Immediate Invalidation: Dead handle kept after onError",
        "description": "onError resets state flag but leaves dead binder handle in memory.",
        "suggestion": "Call destroyRecognizer() immediately inside onError callback."
      }
    ]
    ```
    """
    lens = ResilienceLens(client=DummyClient(fake_json))
    result = lens.analyze(code="var recognizer: SpeechRecognizer? = null", file_path="Manager.kt")

    assert len(result.findings) == 2
    assert result.findings[0].severity == Severity.CRITICAL
    assert result.findings[0].category == Category.RESILIENCE
    assert "Decoupled Lifecycle" in result.findings[0].principle_violated
    assert result.findings[1].severity == Severity.HIGH
    assert result.findings[1].category == Category.RESILIENCE
