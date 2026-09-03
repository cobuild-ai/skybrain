import pytest
from skybrain.review.lenses.ai_conduct import AIConductLens
from skybrain.review.models import Category, Severity


class DummyClient:
    def __init__(self, response_text: str):
        self.response_text = response_text

    def query(self, messages, temperature=0.1, max_tokens=2048):
        return self.response_text


def test_ai_conduct_lens_metadata():
    lens = AIConductLens(client=DummyClient("[]"))
    assert lens.name == "AIConduct"
    assert lens.category == Category.AI_CONDUCT
    assert "Anti-Hardcoding" in lens.system_prompt
    assert "Zero-Hallucination" in lens.system_prompt


def test_ai_conduct_lens_parses_findings():
    fake_json = """
    ```json
    [
      {
        "line": 15,
        "severity": "CRITICAL",
        "principle_violated": "Anti-Hardcoding: Fake mock return detected",
        "description": "The function returns hardcoded fake dict instead of real query.",
        "suggestion": "Implement actual query to database or raise NotImplementedError."
      },
      {
        "line": 42,
        "severity": "HIGH",
        "principle_violated": "No-Silent-Swallowing: Exception swallowed silently",
        "description": "Bare except pass hides real errors.",
        "suggestion": "Log exception with logger.exception and re-raise."
      }
    ]
    ```
    """
    lens = AIConductLens(client=DummyClient(fake_json))
    result = lens.analyze(code="def fake(): return {'status': 'ok'}", file_path="dummy.py")

    assert len(result.findings) == 2
    assert result.findings[0].severity == Severity.CRITICAL
    assert result.findings[0].category == Category.AI_CONDUCT
    assert "Anti-Hardcoding" in result.findings[0].principle_violated
    assert result.findings[1].severity == Severity.HIGH
