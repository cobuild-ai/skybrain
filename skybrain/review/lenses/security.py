"""Security Review Lens — OWASP and defensive programming principles."""

from skybrain.review.lenses.base import Category, ReviewLens


class SecurityLens(ReviewLens):
    """Analyzes code for security vulnerabilities and defensive gaps.

    Focus areas: input validation, error handling, injection,
    sensitive data exposure, and authentication/authorization.
    """

    @property
    def name(self) -> str:
        return "Security"

    @property
    def category(self) -> Category:
        return Category.SECURITY

    @property
    def system_prompt(self) -> str:
        return (
            "You are a senior application security engineer. You perform "
            "code security audits following OWASP guidelines and defensive "
            "programming best practices.\n\n"
            "Analyze the code for these specific vulnerabilities:\n"
            "1. **Input Validation**: Are all external inputs (HTTP params, "
            "file paths, user data) validated and sanitized before use?\n"
            "2. **Error Handling**: Do error messages leak internal paths, "
            "stack traces, or sensitive configuration to clients?\n"
            "3. **Exception Safety**: Are bare `except Exception` blocks "
            "hiding critical errors? Are resources properly released in "
            "finally blocks?\n"
            "4. **Path Traversal**: Can file path parameters be manipulated "
            "to access files outside intended directories?\n"
            "5. **Injection**: Are there string interpolation patterns that "
            "could allow command injection or log injection?\n"
            "6. **Sensitive Data**: Are API keys, tokens, or credentials "
            "hardcoded or logged in plaintext?\n"
            "7. **Race Conditions**: Are shared mutable resources protected "
            "against concurrent access?\n\n"
            "Be precise: cite specific line numbers, input vectors, and "
            "the exact CWE or OWASP category."
        )
