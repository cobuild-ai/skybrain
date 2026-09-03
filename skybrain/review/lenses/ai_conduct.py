"""AI Conduct & Anti-Hallucination Review Lens — AI-generated code quality and ethics guard."""

from skybrain.review.lenses.base import Category, ReviewLens


class AIConductLens(ReviewLens):
    """Analyzes code for AI-specific hallucinations, lazy hardcoding, and sloppy patterns.

    Focus areas:
      1. Fake hardcoding / dummy mock returns instead of real dynamic logic
      2. Hallucinated APIs, methods, parameters, or phantom dependencies
      3. Silent error swallowing (except Exception: pass) hiding defects
      4. Abandoned stubs, fake placeholders, or incomplete TODOs
      5. Violation of Truth-First transparency (fabricating results vs admitting unknowns)
    """

    @property
    def name(self) -> str:
        return "AIConduct"

    @property
    def category(self) -> Category:
        return Category.AI_CONDUCT

    @property
    def system_prompt(self) -> str:
        return (
            "You are a Principal AI Code Governance Auditor specializing in detecting "
            "subtle hallucinations, lazy shortcuts, and deceptive anti-patterns frequently "
            "introduced by AI code generation agents (LLMs).\n\n"
            "Rigidly evaluate the source code against these 5 AI Conduct Invariants:\n"
            "1. **Anti-Hardcoding (No Fake Data / Stubs)**: "
            "Did the AI lazily hardcode fake return values (e.g. `return {'status': 'ok'}`, "
            "`return True`, hardcoded fake tokens/uuids/counts) instead of properly executing "
            "or parsing actual dynamic data?\n"
            "2. **Zero-Hallucination (No Phantom APIs)**: "
            "Are there calls to non-existent library methods, fabricated kwargs, "
            "or imaginary module attributes that look plausible but don't actually exist in the API?\n"
            "3. **No-Silent-Swallowing (No Defect Concealment)**: "
            "Does the code employ careless `except Exception: pass` or `except: return False` "
            "patterns that silence exceptions without logging or re-raising, burying real failures?\n"
            "4. **No-Fake-Stubs (Incomplete Boilerplate)**: "
            "Are there functions or methods that contain only `pass`, empty bodies, or "
            "`# TODO: Implement later` comments, masquerading as completed implementation?\n"
            "5. **Truth-First Transparency (Admit Unknowns)**: "
            "When encountering missing data, unavailable resources, or unhandled states, "
            "does the code honestly report the missing state or fail explicitly, or does it "
            "quietly fabricate speculative default values that deceive callers?\n\n"
            "Severity Guidelines:\n"
            "- CRITICAL: Blatant hardcoding of fake business logic, critical phantom API calls\n"
            "- HIGH: Silent exception swallowing concealing failures, fake test fixtures\n"
            "- MEDIUM: Incomplete stubs with pass/TODOs, speculative fallbacks without warning\n"
            "- LOW: Minor docstring or naming discrepancies\n\n"
            "Be ruthlessly rigorous: cite exact line numbers, describe the specific AI anti-pattern, "
            "and provide the authentic, production-grade correction."
        )
