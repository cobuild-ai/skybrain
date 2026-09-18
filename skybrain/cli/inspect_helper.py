import re
from pathlib import Path
from typing import Dict, List, Optional

def extract_code_skeleton(source_code: str, file_path: Path) -> str:
    """
    Extracts high-level class definitions, function signatures, enums,
    and constants from Kotlin, Java, and Python source files.
    """
    ext = file_path.suffix.lower()
    lines = source_code.splitlines()
    skeleton_lines: List[str] = []

    if ext in (".kt", ".kts", ".java"):
        # Kotlin / Java skeleton extraction
        for idx, line in enumerate(lines):
            stripped = line.strip()
            # Package and imports are skipped to save tokens
            if stripped.startswith("package ") or stripped.startswith("import "):
                continue

            # Class, interface, object, enum declarations
            if re.search(r"\b(class|interface|object|enum\s+class)\s+[A-Za-z0-9_]+", stripped):
                skeleton_lines.append(f"L{idx+1}: {line}")
            # Function signatures
            elif re.search(r"\b(fun|public|private|protected|internal|suspend)\s+.*\(", stripped):
                # Don't take lines inside string literals
                if not stripped.startswith("//") and not stripped.startswith("*"):
                    skeleton_lines.append(f"L{idx+1}: {line}")
            # Constants and StateFlow properties
            elif re.search(r"\b(val|var|const\s+val)\s+[A-Za-z0-9_]+.*StateFlow", stripped):
                skeleton_lines.append(f"L{idx+1}: {line}")

    elif ext == ".py":
        # Python skeleton extraction
        for idx, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("class ") or stripped.startswith("def ") or stripped.startswith("async def "):
                skeleton_lines.append(f"L{idx+1}: {line}")
            elif re.match(r"^[A-Z_0-9]+\s*[:=]", stripped):
                skeleton_lines.append(f"L{idx+1}: {line}")

    else:
        # Generic fallback: first 40 non-empty lines
        for idx, line in enumerate(lines[:40]):
            if line.strip():
                skeleton_lines.append(f"L{idx+1}: {line}")

    if not skeleton_lines:
        return f"// No high-level declarations detected ({len(lines)} total lines)"

    return "\n".join(skeleton_lines[:80])


def inspect_file(
    file_path: Path,
    use_slm: bool = True
) -> str:
    """
    Inspects a source file and returns an ultra-compact summary (Skeleton + 3-line Architecture Summary).
    Saves thousands of cloud tokens by preventing full-file dumps.
    """
    if not file_path.exists():
        return f"❌ File not found: {file_path}"

    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        return f"❌ Failed to read file: {e}"

    total_lines = len(content.splitlines())
    skeleton = extract_code_skeleton(content, file_path)

    summary_header = [
        f"📄 File: {file_path.name} ({total_lines} lines, {round(file_path.stat().st_size / 1024, 1)} KB)",
        "--- [High-Level Architectural Skeleton] ---",
        skeleton,
        "-------------------------------------------"
    ]

    # 로컬 SLM 요약 추가 시도
    if use_slm and total_lines > 50:
        from skybrain.server.supervisor import DaemonSupervisor
        from skybrain.core.config import settings
        import httpx

        prompt = f"""다음 코드의 핵심 책임과 구조를 3줄로 명확하게 요약하세요.
[파일]: {file_path.name}
[코드 개요]:
{skeleton[:1500]}
"""

        if DaemonSupervisor.check_health_fast():
            try:
                url = f"http://{settings.host}:{settings.port}/v1/chat/completions"
                payload = {
                    "model": "default",
                    "messages": [
                        {"role": "system", "content": "You are a concise software architect."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.1,
                    "max_tokens": 256
                }
                resp = httpx.post(url, json=payload, timeout=20.0)
                if resp.status_code == 200:
                    slm_summary = resp.json()["choices"][0]["message"]["content"].strip()
                    summary_header.insert(1, f"🧠 Architecture Summary (by Qwen 3.8):\n{slm_summary}\n")
            except Exception:
                pass

    return "\n".join(summary_header)
