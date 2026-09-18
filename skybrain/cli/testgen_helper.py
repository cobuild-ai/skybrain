from pathlib import Path
from typing import Optional

def generate_test_scaffold(
    source_path: Path,
    target_symbol: Optional[str] = None,
    use_slm: bool = True
) -> str:
    """
    Generates unit test boilerplate (JUnit 4 for Kotlin/Android or pytest for Python)
    using on-device Qwen 3.8 SLM with high-reliability fallback.
    """
    if not source_path.exists():
        return f"// Target file not found: {source_path}"

    content = source_path.read_text(encoding="utf-8", errors="ignore")
    ext = source_path.suffix.lower()

    if use_slm:
        from skybrain.server.supervisor import DaemonSupervisor
        from skybrain.core.config import settings
        import httpx

        test_framework = "JUnit 4 / Assert" if ext in (".kt", ".java") else "pytest"
        symbol_instruction = f"'{target_symbol}' 함수/클래스를 중점적으로" if target_symbol else "핵심 클래스를"

        prompt = f"""당신은 테스트 주도 개발(TDD) 전문가입니다.
다음 소스코드를 분석하여 {test_framework} 기반의 단위 테스트 뼈대(Scaffold)를 작성하세요.
{symbol_instruction} 검증하는 테스트 메서드 3~5개를 작성하세요.

[요구사항]
1. 정직하고 명확한 테스트 케이스 (Zero Fake Protocol)
2. 정상 케이스, 엣지 케이스(빈 문자열/null), 예외 처리 검증 포함
3. 코드 블록만 출력하세요.

[소스 파일]: {source_path.name}
[코드 일부]:
{content[:2500]}
"""

        if DaemonSupervisor.check_health_fast():
            try:
                url = f"http://{settings.host}:{settings.port}/v1/chat/completions"
                payload = {
                    "model": "default",
                    "messages": [
                        {"role": "system", "content": "You are a professional software testing architect."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.2,
                    "max_tokens": 1500
                }
                resp = httpx.post(url, json=payload, timeout=60.0)
                if resp.status_code == 200:
                    test_code = resp.json()["choices"][0]["message"]["content"].strip()
                    if test_code.startswith("```"):
                        import re
                        test_code = re.sub(r"^```[a-zA-Z]*\n", "", test_code)
                        test_code = re.sub(r"\n```$", "", test_code).strip()
                    return test_code
            except Exception:
                pass

    # Fallback template
    if ext in (".kt", ".java"):
        class_name = source_path.stem + "Test"
        return f"""package {source_path.parent.name}

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

class {class_name} {{

    @Test
    fun testBasicFunctionality() {{
        // TODO: Implement test for {source_path.stem}
        assertTrue(true)
    }}

    @Test
    fun testEdgeCasesAndNullSafety() {{
        // TODO: Test edge conditions
        assertTrue(true)
    }}
}}
"""
    else:
        return f"""import pytest

def test_{source_path.stem}_basic():
    # TODO: Implement basic unit test
    assert True

def test_{source_path.stem}_edge_cases():
    # TODO: Implement edge case test
    assert True
"""
